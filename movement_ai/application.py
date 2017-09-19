import time
import numpy
import random
import collections
import threading
from PyQt4 import QtGui, QtCore

from entities.hierarchical import Entity
import tracking.pn.receiver
from fps_meter import FpsMeter
from ui.control_layout import ControlLayout

class Avatar:
    def __init__(self, index, entity, behavior):
        self.index = index
        self.entity = entity
        self.behavior = behavior
        
class Application:
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("--pn-host", default="localhost")
        parser.add_argument("--pn-port", type=int, default=tracking.pn.receiver.SERVER_PORT_BVH)
        parser.add_argument("--pn-convert-to-z-up", action="store_true")
        parser.add_argument("--pn-translation-offset")
        parser.add_argument("--frame-rate", type=float, default=30.0)
        parser.add_argument("--show-fps", action="store_true")
        parser.add_argument("--output-receiver-host")
        parser.add_argument("--output-receiver-port", type=int, default=10000)
        parser.add_argument("--output-receiver-type", choices=["bvh", "world"], default="bvh")
        parser.add_argument("--random-seed", type=int)
        parser.add_argument("--memory-size", type=int, default=500)
        Entity.add_parser_arguments(parser)
        
    def __init__(self, student, avatars, args, receive_from_pn=False, create_entity=None):
        self._student = student
        self._avatars = avatars
        self._args = args
        self.receive_from_pn = receive_from_pn
        self._create_entity = create_entity
        self.show_fps = args.show_fps

    def initialize(self):
        if self._args.random_seed is not None:
            random.seed(self._args.random_seed)

        if self.receive_from_pn:
            self.on_pn_connection_status_changed(False)
            self.try_connect_to_pn()
            
        if self._args.output_receiver_host:
            from connectivity import avatar_osc_sender
            if self._args.output_receiver_type == "world":
                self._output_sender = avatar_osc_sender.AvatarOscWorldSender(
                    self._args.output_receiver_port, self._args.output_receiver_host)
            elif self._args.output_receiver_type == "bvh":
                self._output_sender = avatar_osc_sender.AvatarOscBvhSender(
                    self._args.output_receiver_port, self._args.output_receiver_host)
        else:
            self._output_sender = None
            
        self._training_data = collections.deque([], maxlen=self._args.memory_size)
        self._input = None
        self._desired_frame_duration = 1.0 / self._args.frame_rate
        self._frame_count = 0
        self._previous_frame_time = None
        self._fps_meter = FpsMeter()

    def start_learning_thread(self):
        thread = threading.Thread(target=self._learning_loop)
        thread.daemon = True
        thread.start()
        
    def _learning_loop(self):
        while True:
            input_ = self._input
            student = self._student
            if input_ is None or not self._student.supports_incremental_learning():
                time.sleep(0.001)
                continue
            
            student.train([input_])
            self._training_data.append(input_)
            student.probe(self._training_data)
            time.sleep(0.001)
            
    def try_connect_to_pn(self):
        if self._create_entity is None:
            raise Exception("receive_from_pn requires create_entity to be defined")
        
        def receive_from_pn(pn_entity):
            try:
                for frame in pn_receiver.get_frames():
                    process_frame(frame)
            except tracking.pn.receiver.RemotePeerShutDown:
                print "Lost connection to PN!"
                self.on_pn_connection_status_changed(False)

        def process_frame(frame):
            input_from_pn = pn_entity.get_value_from_frame(
                frame, convert_to_z_up=self._args.pn_convert_to_z_up)
            input_from_pn[0:3] += pn_translation_offset
            self.set_input(input_from_pn)

        pn_receiver = tracking.pn.receiver.PnReceiver()
        print "connecting to PN server..."
        try:
            pn_receiver.connect(self._args.pn_host, self._args.pn_port)
        except Exception as exception:
            print "Failed: %s" % exception
            return
        print "ok"
        self.on_pn_connection_status_changed(True)
        pn_entity = self._create_entity()
        if self._args.pn_translation_offset:
            pn_translation_offset = numpy.array(
                [float(string) for string in self._args.pn_translation_offset.split(",")])
        else:
            pn_translation_offset = numpy.array([0,0,0])
        pn_receiver_thread = threading.Thread(target=lambda: receive_from_pn(pn_entity))
        pn_receiver_thread.daemon = True
        pn_receiver_thread.start()

    def on_pn_connection_status_changed(self, status):
        pass
    
    def main_loop(self):
        while True:
            self._frame_start_time = time.time()
            self.update()
            self._wait_until_next_frame_is_timely()

    def set_input(self, input_):
        self._input = input_

    def set_student(self, student):
        self._student = student

    def update_if_timely(self):
        if self._previous_frame_time is None or \
           time.time() - self._previous_frame_time >= self._desired_frame_duration:
            self.update()

    def update(self):
        now = time.time()
        
        for avatar in self._avatars:
            if self._input is not None and self._student.supports_incremental_learning():
                avatar.behavior.set_normalized_observed_reductions(self._student.normalized_observed_reductions)
            avatar.behavior.proceed(self._desired_frame_duration)
            avatar.entity.update()
            if self._input is not None:
                avatar.behavior.on_input(self._input)
            output = None
            if avatar.behavior.sends_output():
                output = avatar.behavior.get_output()
            else:
                reduction = avatar.behavior.get_reduction()
                if reduction is not None:
                    output = self._student.inverse_transform(numpy.array([reduction]))[0]
            if output is not None:
                if self._output_sender is not None:
                    self._send_output(avatar, output)

        self._previous_frame_time = now
        self._frame_count += 1
        if self.show_fps:
            self._fps_meter.update()

    @property
    def training_data_size(self):
        return len(self._training_data)

    def _send_output(self, avatar, output):
        self._output_sender.send_frame(avatar.index, output, avatar.entity)

    def _wait_until_next_frame_is_timely(self):
        frame_duration = time.time() - self._frame_start_time
        if frame_duration < self._desired_frame_duration:
            time.sleep(self._desired_frame_duration - frame_duration)

    def reset_student(self):
        self._student.reset()
        
    def reset_output_sender(self):
        self._output_sender.reset()

    def on_changed_friction(self, value):
        pass
        
class Memory:
    def __init__(self):
        self.clear()

    def clear(self):
        self.frames = []

    def on_input(self, input_):
        self.frames.append(input_)

    def get_num_frames(self):
        return len(self.frames)

    def create_random_recall(self, num_frames_to_recall, reverse_recall_probability=0):
        if random.uniform(0.0, 1.0) < reverse_recall_probability:
            return self._create_reverse_recall(num_frames_to_recall)
        else:
            return self._create_normal_recall(num_frames_to_recall)

    def _create_normal_recall(self, num_frames_to_recall):
        max_cursor = self.get_num_frames() - num_frames_to_recall
        cursor = int(random.random() * max_cursor)
        time_direction = 1
        print "normal recall from %s" % cursor
        return Recall(self, cursor, time_direction)

    def _create_reverse_recall(self, num_frames_to_recall):
        max_cursor = self.get_num_frames() - num_frames_to_recall
        cursor = int(random.random() * max_cursor) + num_frames_to_recall
        time_direction = -1
        print "reverse recall from %s" % cursor
        return Recall(self, cursor, time_direction)

class Recall:
    def __init__(self, memory, cursor, time_direction):
        self._memory = memory
        self._cursor = cursor
        self._time_direction = time_direction
        
    def proceed(self, num_frames):
        self._cursor += num_frames * self._time_direction

    def get_output(self):
        return self._memory.frames[self._cursor]

class BaseUiWindow(QtGui.QWidget):
    def __init__(self, application, master_behavior):
        QtGui.QWidget.__init__(self)
        self._application = application
        self._master_behavior = master_behavior
        self._control_layout = ControlLayout()
        self.setLayout(self._control_layout.layout)
        if application.receive_from_pn:
            self._add_pn_connection_status()
        self._add_training_data_size_label()
        self._create_menu()

        application.on_pn_connection_status_changed = self._update_pn_connection_status_label
        
        timer = QtCore.QTimer(self)
        QtCore.QObject.connect(timer, QtCore.SIGNAL('timeout()'), self._update)
        timer.start()

    def _update(self):
        self._application.update_if_timely()
        self._update_training_data_size_label()

    def _add_training_data_size_label(self):
        self._control_layout.add_label("Training data size")
        self._training_data_size_label = QtGui.QLabel("")
        self._control_layout.add_control_widget(self._training_data_size_label)

    def _update_training_data_size_label(self):
        self._training_data_size_label.setText("%d" % self._application.training_data_size)

    def _add_pn_connection_status(self):
        self._control_layout.add_label("PN connection")
        self._pn_connection_status_label = QtGui.QLabel("")
        self._control_layout.add_control_widget(self._pn_connection_status_label)

    def _update_pn_connection_status_label(self, status):
        if status == True:
            self._pn_connection_status_label.setText("Connected")
            self._pn_connection_status_label.setStyleSheet("QLabel { background-color : green; }")
        else:
            self._pn_connection_status_label.setText("Disconnected")
            self._pn_connection_status_label.setStyleSheet("QLabel { background-color : red; }")
            
    def _create_menu(self):
        self._menu_bar = QtGui.QMenuBar()
        self._control_layout.layout.setMenuBar(self._menu_bar)
        self._create_main_menu()

    def _create_main_menu(self):
        self._main_menu = self._menu_bar.addMenu("&Main")
        if self._application.receive_from_pn:
            self._add_connect_to_pn_action()
        self._add_reset_model_action()
        self._add_reset_output_sender_action()
        self._add_show_fps_action()
        self._add_quit_action()

    def _add_connect_to_pn_action(self):
        action = QtGui.QAction("Connect to PN", self)
        action.triggered.connect(self._application.try_connect_to_pn)
        self._main_menu.addAction(action)
        
    def _add_reset_model_action(self):
        action = QtGui.QAction("Reset model", self)
        action.triggered.connect(self._application.reset_student)
        self._main_menu.addAction(action)
        
    def _add_reset_output_sender_action(self):
        action = QtGui.QAction('Reset OSC sender', self)
        action.triggered.connect(self._application.reset_output_sender)
        self._main_menu.addAction(action)

    def _add_show_fps_action(self):
        def on_triggered(checked):
            self._application.show_fps = checked
        
        action = QtGui.QAction("Show frame rate", self)
        action.setCheckable(True)
        action.setChecked(self._application.show_fps)
        action.triggered.connect(lambda checked: on_triggered(checked))
        self._main_menu.addAction(action)

    def _add_quit_action(self):
        action = QtGui.QAction("&Quit", self)
        action.triggered.connect(QtGui.QApplication.exit)
        self._main_menu.addAction(action)
        
