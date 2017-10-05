import time
import numpy
import random
import collections
import threading
import logging
from PyQt4 import QtGui, QtCore

from entities.hierarchical import Entity
import tracking.pn.receiver
from fps_meter import FpsMeter
from ui.control_layout import ControlLayout
from bvh.bvh_writer import BvhWriter

FpsMeter.print_fps = False

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
        parser.add_argument("--output-receiver-host")
        parser.add_argument("--output-receiver-port", type=int, default=10000)
        parser.add_argument("--output-receiver-type", choices=["bvh", "world"], default="bvh")
        parser.add_argument("--random-seed", type=int)
        parser.add_argument("--memory-size", type=int, default=100)
        parser.add_argument("--training-data-interval", type=int, default=5)
        Entity.add_parser_arguments(parser)
        
    def __init__(self, student, avatars, args, receive_from_pn=False, create_entity=None):
        self._student = student
        self._avatars = avatars
        self.args = args
        self.receive_from_pn = receive_from_pn
        self._create_entity = create_entity
        self._logger = logging.getLogger(self.__class__.__name__)
        self._pn_receiver = None

    def initialize(self):
        if self.args.random_seed is not None:
            random.seed(self.args.random_seed)

        if self.receive_from_pn:
            self.on_pn_connection_status_changed(False)
            self.try_connect_to_pn()
            
        if self.args.output_receiver_host:
            from connectivity import avatar_osc_sender
            if self.args.output_receiver_type == "world":
                self._output_sender = avatar_osc_sender.AvatarOscWorldSender(
                    self.args.output_receiver_port, self.args.output_receiver_host)
            elif self.args.output_receiver_type == "bvh":
                self._output_sender = avatar_osc_sender.AvatarOscBvhSender(
                    self.args.output_receiver_port, self.args.output_receiver_host)
        else:
            self._output_sender = None

        self._training_data = collections.deque([], maxlen=self.args.memory_size)
        self._input = None
        self._desired_frame_duration = 1.0 / self.args.frame_rate
        self._frame_count = 0
        self._previous_frame_time = None
        self._fps_meter = FpsMeter("output")
        self._is_recording = False
        self._recorded_outputs = []

    def try_connect_to_pn(self):
        if self._create_entity is None:
            raise Exception("receive_from_pn requires create_entity to be defined")
        
        def receive_from_pn(pn_entity):
            try:
                for frame in self._pn_receiver.get_frames():
                    process_frame(frame)
            except tracking.pn.receiver.RemotePeerShutDown:
                self.print_and_log("Lost connection to PN!")
                self.on_pn_connection_status_changed(False)

        def process_frame(frame):
            input_from_pn = pn_entity.get_value_from_frame(
                frame, convert_to_z_up=self.args.pn_convert_to_z_up)
            input_from_pn[0:3] += pn_translation_offset
            self.set_input(input_from_pn)

        self._pn_receiver = tracking.pn.receiver.PnReceiver()
        self._pn_receiver.on_fps_changed = self.on_pn_fps_changed
        self.print_and_log("connecting to PN server...")
        try:
            self._pn_receiver.connect(self.args.pn_host, self.args.pn_port)
        except Exception as exception:
            self.print_and_log("Failed: %s" % exception)
            return
        self.print_and_log("ok")
        self.on_pn_connection_status_changed(True)
        pn_entity = self._create_entity()
        if self.args.pn_translation_offset:
            pn_translation_offset = numpy.array(
                [float(string) for string in self.args.pn_translation_offset.split(",")])
        else:
            pn_translation_offset = numpy.array([0,0,0])
        pn_receiver_thread = threading.Thread(target=lambda: receive_from_pn(pn_entity))
        pn_receiver_thread.daemon = True
        pn_receiver_thread.start()

    def on_pn_connection_status_changed(self, status):
        pass

    def on_pn_fps_changed(self, fps):
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
        try:
            if self._previous_frame_time is None or \
               time.time() - self._previous_frame_time >= self._desired_frame_duration:
                self.update()
        except Exception as exception:
            print "EXCEPTION:", exception
            self._logger.error(exception, exc_info=True)

    def update(self):
        now = time.time()
        if self._input is not None and self._student.supports_incremental_learning():
            self._student.train([self._input])
            if self._frame_count % self.args.training_data_interval == 0:
                self._training_data.append(self._input)
                self._student.probe(self._training_data)
        
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
                    self._send_output_and_handle_sender_status(avatar, output)
                if self._is_recording:
                    self._add_to_bvh(avatar, output)

        self._previous_frame_time = now
        self._frame_count += 1
        self._fps_meter.update()
        self.on_output_fps_changed(self._fps_meter.get_fps())

    def on_output_fps_changed(self, fps):
        pass
    
    @property
    def training_data_size(self):
        return len(self._training_data)

    def _send_output_and_handle_sender_status(self, avatar, output):
        self._output_sender.send_frame(avatar.index, output, avatar.entity)
        status = self._output_sender.get_status()
        self.on_output_sender_status_changed(status)

    def on_output_sender_status_changed(self):
        pass

    def _add_to_bvh(self, avatar, output):
        self._logger.debug("_add_to_bvh with index %s" % self._recording_frame_index)
        self._recorded_outputs.append(output)
        self._recording_frame_index += 1
        
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

    def print_and_log(self, message):
        print message
        self._logger.info(message)

    def start_recording(self):
        self._logger.debug("start_recording()")
        self._recording_path = "recordings/%s.bvh" % time.strftime("%Y_%d_%m_%H%M%S")
        self._logger.debug("recording path: %s" % self._recording_path)
        print "Recording to %s" % self._recording_path
        self._bvh_writer = BvhWriter(
            self._avatars[0].entity.bvh_reader.get_hierarchy(), self._desired_frame_duration)
        self._recording_frame_index = 0
        self._recorded_outputs = []
        self._is_recording = True

    def stop_recording(self):
        self._logger.debug("stop_recording()")
        self._logger.debug("recording path: %s" % self._recording_path)
        print "Writing %s ..." % self._recording_path
        avatar = self._avatars[0]
        for output in self._recorded_outputs:
            avatar.entity.parameters_to_processed_pose(output, avatar.entity.pose)
            self._bvh_writer.add_pose_as_frame(avatar.entity.pose)
        self._bvh_writer.write(self._recording_path)
        print "OK"
        self._is_recording = False
        
class Memory:
    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.clear()

    def clear(self):
        self._logger.debug("clear()")
        self.set_frames([])

    def set_frames(self, frames):
        self._logger.debug("set_frames(frames=...) len(frames)=%s" % len(frames))
        self._frames = frames
        self.on_frames_changed()
        
    def on_input(self, frame):
        self._logger.debug("on_input(...)")
        self._frames.append(frame)
        self.on_frames_changed()

    def get_num_frames(self):
        return len(self._frames)

    def get_frames(self):
        return self._frames
    
    def get_frame_by_index(self, index):
        self._logger.debug("get_frame_by_index(%s)" % index)
        
        if index < 0:
            self._warn_and_log("get_frame_by_index called with negative index. Returning first element.")
            index = 0
        elif index >= len(self._frames):
            self._warn_and_log("get_frame_by_index called with too high index. Returning last element.")
            index = -1
            
        return self._frames[index]

    def _warn_and_log(self, message):
        print "WARNING: %s" % message
        self._logger.warn(message)
        
    def create_random_recall(self, num_frames_to_recall,
                             reverse_recall_probability=0,
                             recency_num_frames=None):
        self._logger.debug(
            "create_random_recall(num_frames_to_recall=%s, reverse_recall_probability=%s, recency_num_frames=%s)" % (
                num_frames_to_recall, reverse_recall_probability, recency_num_frames))
        if random.uniform(0.0, 1.0) < reverse_recall_probability:
            return self._create_reverse_recall(num_frames_to_recall)
        else:
            return self._create_normal_recall(num_frames_to_recall, recency_num_frames)

    def _create_normal_recall(self, num_frames_to_recall, recency_num_frames=None):
        if recency_num_frames is None:
            recency_num_frames = self.get_num_frames()
        else:
            if recency_num_frames > self.get_num_frames():
                recency_num_frames = self.get_num_frames()
            if recency_num_frames < num_frames_to_recall:
                recency_num_frames = num_frames_to_recall
    
        min_cursor = self.get_num_frames() - recency_num_frames
        max_cursor = self.get_num_frames() - num_frames_to_recall
        cursor = random.randint(min_cursor, max_cursor)
        time_direction = 1
        self._logger.debug("normal recall from %s" % cursor)
        return Recall(self, cursor, time_direction)

    def _create_reverse_recall(self, num_frames_to_recall):
        max_cursor = max(self.get_num_frames() - num_frames_to_recall, 0)
        cursor = random.randint(0, max_cursor) + num_frames_to_recall
        time_direction = -1
        self._logger.debug("reverse recall from %s" % cursor)
        return Recall(self, cursor, time_direction)

    def on_frames_changed(self):
        pass
        
class Recall:
    def __init__(self, memory, cursor, time_direction):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.debug("__init__(memory=..., cursor=%s, time_direction=%s) memory.get_num_frames()=%s" % (
            cursor, time_direction, memory.get_num_frames()))
        self._memory = memory
        self._cursor = cursor
        self._time_direction = time_direction
        
    def proceed(self, num_frames):
        self._logger.debug("proceed(%s)" % num_frames)
        self._cursor += num_frames * self._time_direction

    def get_output(self):
        self._logger.debug("get_output()")
        return self._memory.get_frame_by_index(self._cursor)

class BaseUiWindow(QtGui.QWidget):
    def __init__(self, application, master_behavior):
        QtGui.QWidget.__init__(self)
        self._application = application
        self._master_behavior = master_behavior
        self._control_layout = ControlLayout()
        self.setLayout(self._control_layout.layout)
        if application.receive_from_pn:
            self._add_pn_connection_status()
            self._add_pn_fps_label()
            application.on_pn_fps_changed = self._update_pn_fps_label
        if application.args.output_receiver_host:
            self._add_output_sender_status()
        self._add_output_fps_label()
        self._add_training_data_size_label()
        self._create_menu()

        application.on_pn_connection_status_changed = self._update_pn_connection_status_label
        application.on_output_sender_status_changed = self._update_output_sender_status_label
        application.on_output_fps_changed = self._update_output_fps_label
        
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

    def _add_pn_fps_label(self):
        self._control_layout.add_label("PN frame rate")
        self._pn_fps_label = QtGui.QLabel("")
        self._control_layout.add_control_widget(self._pn_fps_label)

    def _update_pn_fps_label(self, fps):
        if fps is not None:
            self._pn_fps_label.setText("%.1f" % fps)
        
    def _add_output_sender_status(self):
        self._control_layout.add_label("OSC sender status")
        self._output_sender_status_label = QtGui.QLabel("")
        self._control_layout.add_control_widget(self._output_sender_status_label)

    def _update_output_sender_status_label(self, status):
        if status == True:
            self._output_sender_status_label.setText("OK")
            self._output_sender_status_label.setStyleSheet("QLabel { background-color : green; }")
        else:
            self._output_sender_status_label.setText("Error")
            self._output_sender_status_label.setStyleSheet("QLabel { background-color : red; }")

    def _add_output_fps_label(self):
        self._control_layout.add_label("Output frame rate")
        self._output_fps_label = QtGui.QLabel("")
        self._control_layout.add_control_widget(self._output_fps_label)

    def _update_output_fps_label(self, fps):
        if fps is not None:
            self._output_fps_label.setText("%.1f" % fps)
            
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
        self._add_start_recording_action()
        self._add_stop_recording_action()
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

    def _add_quit_action(self):
        action = QtGui.QAction("&Quit", self)
        action.triggered.connect(QtGui.QApplication.exit)
        self._main_menu.addAction(action)

    def _add_start_recording_action(self):
        def start_recording():
            self._start_recording_action.setEnabled(False)
            self._stop_recording_action.setEnabled(True)
            self._application.start_recording()
            
        self._start_recording_action = QtGui.QAction("Start &recording", self)
        self._start_recording_action.triggered.connect(start_recording)
        self._main_menu.addAction(self._start_recording_action)

    def _add_stop_recording_action(self):
        def stop_recording():
            self._start_recording_action.setEnabled(True)
            self._stop_recording_action.setEnabled(False)
            self._application.stop_recording()
            
        self._stop_recording_action = QtGui.QAction("Stop &recording", self)
        self._stop_recording_action.triggered.connect(stop_recording)
        self._stop_recording_action.setEnabled(False)
        self._main_menu.addAction(self._stop_recording_action)
        
def set_up_logging():
    logging.basicConfig(
        format="%(asctime)s %(name)-20s %(levelname)-8s %(message)s",
        level=logging.DEBUG,
        filename="logs/application.log",
        filemode="w")
