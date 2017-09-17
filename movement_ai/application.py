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
        parser.add_argument("--frame-rate", type=float, default=50.0)
        parser.add_argument("--show-fps", action="store_true")
        parser.add_argument("--output-receiver-host")
        parser.add_argument("--output-receiver-port", type=int, default=10000)
        parser.add_argument("--output-receiver-type", choices=["bvh", "world"], default="bvh")
        parser.add_argument("--random-seed", type=int)
        parser.add_argument("--memory-size", type=int, default=1000)
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
            self._setup_pn_connection()
            
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

    def _setup_pn_connection(self):
        if self._create_entity is None:
            raise Exception("receive_from_pn requires create_entity to be defined")
        
        def receive_from_pn(pn_entity):
            try:
                for frame in pn_receiver.get_frames():
                    process_frame(frame)
            except tracking.pn.receiver.RemotePeerShutDown:
                print "Lost connection to PN!"
                self.on_pn_connection_status_changed("Disconnected")

        def process_frame(frame):
            input_from_pn = pn_entity.get_value_from_frame(
                frame, convert_to_z_up=self._args.pn_convert_to_z_up)
            input_from_pn[0:3] += pn_translation_offset
            self.set_input(input_from_pn)

        pn_receiver = tracking.pn.receiver.PnReceiver()
        print "connecting to PN server..."
        pn_receiver.connect(self._args.pn_host, self._args.pn_port)
        print "ok"
        self.on_pn_connection_status_changed("Connected")
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
        if self._input is not None and self._student.supports_incremental_learning():
            self._student.train([self._input])
            self._training_data.append(self._input)
            self._student.probe(self._training_data)
            self.on_training_data_changed()
        
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

    def on_training_data_changed(self):
        pass
    
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

        application.on_training_data_changed = self._update_training_data_size_label
        application.on_pn_connection_status_changed = self._update_pn_connection_status_label
        
        timer = QtCore.QTimer(self)
        QtCore.QObject.connect(timer, QtCore.SIGNAL('timeout()'), application.update_if_timely)
        timer.start()

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
        self._pn_connection_status_label.setText(status)
        
    def _create_menu(self):
        self._menu_bar = QtGui.QMenuBar()
        self._control_layout.layout.setMenuBar(self._menu_bar)
        self._create_main_menu()

    def _create_main_menu(self):
        self._main_menu = self._menu_bar.addMenu("&Main")
        self._add_reset_model_action()
        self._add_reset_output_sender_action()
        self._add_show_fps_action()
        self._add_quit_action()

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
        
