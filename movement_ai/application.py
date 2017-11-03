import time
import numpy
import random
import collections
import threading
import logging
from PyQt4 import QtGui, QtCore, QtOpenGL
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import math
import copy

from entities.hierarchical import Entity
import tracking.pn.receiver
from fps_meter import FpsMeter
from ui.control_layout import ControlLayout
from ui.floor_checkerboard import FloorCheckerboard
from bvh.bvh_writer import BvhWriter

FLOOR_ARGS = {"num_cells": 26, "size": 26,
              "board_color1": (.2, .2, .2, 1),
              "board_color2": (.3, .3, .3, 1),
              "floor_color": None,
              "background_color": (0.0, 0.0, 0.0, 0.0)}
CAMERA_Y_SPEED = .01
CAMERA_KEY_SPEED = .1
CAMERA_DRAG_SPEED = .1
LOG_HEIGHT = 50

FpsMeter.print_fps = False

class Avatar:
    def __init__(self, index, entity, behavior):
        self.index = index
        self.entity = entity
        self.behavior = behavior
        
class Application:
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("--pn-address",
                            default=["localhost:%s" % tracking.pn.receiver.SERVER_PORT_BVH],
                            help="hostname:port",
                            nargs="+")
        parser.add_argument("--pn-convert-to-z-up", action="store_true")
        parser.add_argument("--pn-translation-offset")
        parser.add_argument("--frame-rate", type=float, default=30.0)
        parser.add_argument("--output-receiver-host")
        parser.add_argument("--output-receiver-port", type=int, default=10000)
        parser.add_argument("--random-seed", type=int)
        parser.add_argument("--memory-size", type=int, default=100)
        parser.add_argument("--training-data-interval", type=int, default=5)
        parser.add_argument("--camera", help="posX,posY,posZ,orientY,orientX",
                            default="-3.767,-1.400,-3.485,-71.900,4.800")
        Entity.add_parser_arguments(parser)
        
    def __init__(self, student, avatars, args, receive_from_pn=False, create_entity=None, z_up=False):
        self._student = student
        self._avatars = avatars
        self.args = args
        self.receive_from_pn = receive_from_pn
        self._create_entity = create_entity
        self.z_up = z_up
        self._logger = logging.getLogger(self.__class__.__name__)
        self._pn_receiver = None
        self._connected_to_pn = False

    @property
    def avatars(self):
        return self._avatars
    
    @property
    def can_create_entity(self):
        return self._create_entity is not None
    
    def create_entity(self):
        return self._create_entity()
    
    def initialize(self, ui_window=None):
        self._ui_window = ui_window
        
        if self.args.random_seed is not None:
            random.seed(self.args.random_seed)

        if self.receive_from_pn:
            self._pn_entity = self._create_entity()
            if self.args.pn_translation_offset:
                self._pn_translation_offset = numpy.array(
                    [float(string) for string in self.args.pn_translation_offset.split(",")])
            else:
                self._pn_translation_offset = numpy.array([0,0,0])
            self._pn_frame = None
            self.on_pn_connection_status_changed(False)
            self.try_connect_to_pn(self.args.pn_address[0])
            
        if self.args.output_receiver_host:
            from connectivity import avatar_osc_sender
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

    def try_connect_to_pn(self, pn_address):
        if self._create_entity is None:
            raise Exception("receive_from_pn requires create_entity to be defined")
        
        def receive_from_pn():
            try:
                for frame in self._pn_receiver.get_frames():
                    self.set_pn_frame(frame)
            except tracking.pn.receiver.RemotePeerShutDown:
                self.print_and_log("Lost connection to PN!")
                self.on_pn_connection_status_changed(False)

        def on_status_message(message):
            self.print_and_log(message)
            
        pn_host, pn_port_string = pn_address.split(":")
        pn_port = int(pn_port_string)
        
        self._disconnect_from_pn_if_connected()
        self._pn_receiver = tracking.pn.receiver.PnReceiver()
        self._pn_receiver.on_fps_changed = self.on_pn_fps_changed
        self._pn_receiver.on_status_message = on_status_message
        self.print_and_log("Connecting to PN server at %s ..." % pn_address)
        
        try:
            self._pn_receiver.connect(pn_host, pn_port)
        except Exception as exception:
            self.print_and_log("Connection to PN server at %s failed: %s" % (pn_address, exception))
            return
        self._connected_to_pn = True
        self.print_and_log("Succesfully connected to PN server at %s" % pn_address)
        self.on_pn_connection_status_changed(True)
        pn_receiver_thread = threading.Thread(target=receive_from_pn)
        pn_receiver_thread.daemon = True
        pn_receiver_thread.start()

    def _disconnect_from_pn_if_connected(self):
        if self._connected_to_pn:
            self.print_and_log("Disconnecting from PN server")
            try:
                self._pn_receiver.stop()
            except Exception as exception:
                self.print_and_log("Stopping PN server failed: %s" % exception)
                return
            self._connected_to_pn = False
            
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

    def set_pn_frame(self, frame):
        self._pn_frame = frame
        
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

        if self._pn_frame is not None:
            self._process_pn_frame(self._pn_frame)
            
        if self._input is not None and self._student.supports_incremental_learning() and self._student.get_learning_rate() > 0:
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
                avatar.entity.parameters_to_processed_pose(output, avatar.entity.pose)
                self._ui_window.on_output_pose(avatar.entity.pose)
                if self._output_sender is not None:
                    self._send_output_and_handle_sender_status(avatar)
                if self._is_recording:
                    self._add_to_bvh(avatar)

        self._previous_frame_time = now
        self._frame_count += 1
        self._fps_meter.update()
        self.on_output_fps_changed(self._fps_meter.get_fps())

    def _process_pn_frame(self, frame):
        input_from_pn = self._pn_entity.get_value_from_frame(
            frame, convert_to_z_up=self.args.pn_convert_to_z_up)
        input_from_pn[0:3] += self._pn_translation_offset
        self.set_input(input_from_pn)

    def on_output_fps_changed(self, fps):
        pass
    
    @property
    def training_data_size(self):
        return len(self._training_data)

    def _send_output_and_handle_sender_status(self, avatar):
        self._output_sender.send_frame(avatar.index, avatar.entity.pose, avatar.entity)
        status = self._output_sender.get_status()
        self.on_output_sender_status_changed(status)

    def on_output_sender_status_changed(self):
        pass

    def _add_to_bvh(self, avatar):
        self._logger.debug("_add_to_bvh with index %s" % self._recording_frame_index)
        self._bvh_writer.add_pose_as_frame(avatar.entity.pose)
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
        timestamped_message = "%s %s" % (time.strftime("%Y-%d-%m %H:%M:%S"), message)
        print timestamped_message
        self._ui_window.append_to_log_widget(timestamped_message + "\n")
        self._logger.info(message)

    def start_recording(self):
        self._logger.debug("start_recording()")
        self._bvh_writer = BvhWriter(
            self._avatars[0].entity.bvh_reader.get_hierarchy(), self._desired_frame_duration)
        self._recording_frame_index = 0
        self._is_recording = True
        print "Started recording"

    def stop_recording(self):
        self._logger.debug("stop_recording()")
        path = "recordings/%s.bvh" % time.strftime("%Y_%d_%m_%H%M%S")
        self._logger.debug("recording path: %s" % path)
        self._is_recording = False
        print "Stopped recording"

        def save_recording():
            print "Writing %s ..." % path
            self._bvh_writer.write(path)
            print "Finished writing %s" % path

        thread = threading.Thread(target=save_recording)
        thread.start()
                
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
        self._logger.debug("recency_num_frames=%s" % recency_num_frames)
        self._logger.debug("min_cursor=%s" % min_cursor)
        self._logger.debug("max_cursor=%s" % max_cursor)
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

        self._main_layout = QtGui.QHBoxLayout()
        self._main_layout.setSpacing(0)
        self._main_layout.setMargin(0)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        
        panel_layout = QtGui.QVBoxLayout()
        
        self._standard_control_layout = ControlLayout()
        self._standard_control_layout_widget = QtGui.QWidget()
        self._standard_control_layout_widget.setLayout(self._standard_control_layout.layout)
        panel_layout.addWidget(self._standard_control_layout_widget)
        
        self._advanced_control_layout = ControlLayout()
        self._advanced_control_layout_widget = QtGui.QWidget()
        self._advanced_control_layout_widget.setLayout(self._advanced_control_layout.layout)
        panel_layout.addWidget(self._advanced_control_layout_widget)
        self._advanced_control_layout_widget.setVisible(False)

        self._log_widget = LogWidget(self)
        panel_layout.addWidget(self._log_widget)
        
        self._main_layout.addLayout(panel_layout)

        self._output_scene = OutputScene(application.avatars[0].entity, application)
        self.set_view_output(False)
        self._main_layout.addWidget(self._output_scene)
        self.setLayout(self._main_layout)
        
        if application.receive_from_pn:
            self._add_pn_address_selector()
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

    def set_view_output(self, enabled):
        self._view_output = enabled
        self._output_scene.set_enabled(enabled)

    def _update(self):
        self._application.update_if_timely()
        self._update_training_data_size_label()

    def _add_training_data_size_label(self):
        self._standard_control_layout.add_label("Training data size")
        self._training_data_size_label = QtGui.QLabel("")
        self._standard_control_layout.add_control_widget(self._training_data_size_label)

    def _update_training_data_size_label(self):
        self._training_data_size_label.setText("%d" % self._application.training_data_size)

    def _add_pn_address_selector(self):
        def create_combobox():
            combobox = QtGui.QComboBox()
            for address in self._application.args.pn_address:
                combobox.addItem(address)
            return combobox

        def create_connect_button():
            def on_clicked():
                pn_address = self._application.args.pn_address[self._pn_selector_combobox.currentIndex()]
                self._application.try_connect_to_pn(pn_address)

            button = QtGui.QPushButton(text="Connect")
            button.clicked.connect(on_clicked)
            return button
            
        self._pn_selector_combobox = create_combobox()
        self._standard_control_layout.add_label("PN address")
        self._standard_control_layout.add_control_widgets(
            [self._pn_selector_combobox, create_connect_button()])
        
    def _add_pn_connection_status(self):
        self._standard_control_layout.add_label("PN connection")
        self._pn_connection_status_label = QtGui.QLabel("")
        self._standard_control_layout.add_control_widget(self._pn_connection_status_label)

    def _update_pn_connection_status_label(self, status):
        if status == True:
            self._pn_connection_status_label.setText("Connected")
            self._pn_connection_status_label.setStyleSheet("QLabel { background-color : green; }")
        else:
            self._pn_connection_status_label.setText("Disconnected")
            self._pn_connection_status_label.setStyleSheet("QLabel { background-color : red; }")

    def _add_pn_fps_label(self):
        self._standard_control_layout.add_label("PN frame rate")
        self._pn_fps_label = QtGui.QLabel("")
        self._standard_control_layout.add_control_widget(self._pn_fps_label)

    def _update_pn_fps_label(self, fps):
        if fps is not None:
            self._pn_fps_label.setText("%.1f" % fps)
        
    def _add_output_sender_status(self):
        self._standard_control_layout.add_label("OSC sender status")
        self._output_sender_status_label = QtGui.QLabel("")
        self._standard_control_layout.add_control_widget(self._output_sender_status_label)

    def _update_output_sender_status_label(self, status):
        if status == True:
            self._output_sender_status_label.setText("OK")
            self._output_sender_status_label.setStyleSheet("QLabel { background-color : green; }")
        else:
            self._output_sender_status_label.setText("Error")
            self._output_sender_status_label.setStyleSheet("QLabel { background-color : red; }")

    def _add_output_fps_label(self):
        self._standard_control_layout.add_label("Output frame rate")
        self._output_fps_label = QtGui.QLabel("")
        self._standard_control_layout.add_control_widget(self._output_fps_label)

    def _update_output_fps_label(self, fps):
        if fps is not None:
            self._output_fps_label.setText("%.1f" % fps)
            
    def _create_menu(self):
        self._menu_bar = QtGui.QMenuBar()
        self._main_layout.setMenuBar(self._menu_bar)
        self._create_main_menu()
        self._create_view_menu()

    def _create_main_menu(self):
        self._main_menu = self._menu_bar.addMenu("&Main")
        self._add_reset_model_action()
        self._add_reset_output_sender_action()
        if self._application.can_create_entity:
            self._add_start_recording_action()
            self._add_stop_recording_action()
        self._add_quit_action()
        
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
        
    def _create_view_menu(self):
        self._view_menu = self._menu_bar.addMenu("View")
        self._add_output_action()
        self._add_camera_actions()
        self._add_advanced_controls_action()

    def _add_output_action(self):
        def on_toggled(action):
            self.set_view_output(action.isChecked())
            
        action = QtGui.QAction("Output", self)
        action.setCheckable(True)
        action.setShortcut("Tab")
        action.toggled.connect(lambda: on_toggled(action))
        self._view_menu.addAction(action)

    def _add_camera_actions(self):
        def add_camera_action(shortcut, key, name):
            action = QtGui.QAction(name, self)
            action.setShortcut(shortcut)
            action.triggered.connect(lambda: self._output_scene.key_pressed(key))
            self._view_menu.addAction(action)
            
        add_camera_action("A", QtCore.Qt.Key_A, "Camera left")
        add_camera_action("D", QtCore.Qt.Key_D, "Camera right")
        add_camera_action("W", QtCore.Qt.Key_W, "Camera front")
        add_camera_action("S", QtCore.Qt.Key_S, "Camera back")
        
    def _add_advanced_controls_action(self):
        def on_toggled(action):
            self._advanced_control_layout_widget.setVisible(action.isChecked())
            
        action = QtGui.QAction("Advanced controls", self)
        action.setCheckable(True)
        action.toggled.connect(lambda: on_toggled(action))
        self._view_menu.addAction(action)

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

    def on_output_pose(self, pose):
        if self._view_output:
            self._output_scene.set_pose(pose)

    def append_to_log_widget(self, string):
        QtGui.QApplication.postEvent(self, CustomQtEvent(lambda: self._log_widget.append(string)))

    def customEvent(self, custom_qt_event):
        custom_qt_event.callback()

class CustomQtEvent(QtCore.QEvent):
    EVENT_TYPE = QtCore.QEvent.Type(QtCore.QEvent.registerEventType())

    def __init__(self, callback):
        QtCore.QEvent.__init__(self, CustomQtEvent.EVENT_TYPE)
        self.callback = callback

class LogWidget(QtGui.QTextEdit):
    def __init__(self, *args, **kwargs):
        QtGui.QTextEdit.__init__(self, *args, **kwargs)
        self.setReadOnly(True)

    def append(self, string):
        self.insertPlainText(string)
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def sizeHint(self):
        return QtCore.QSize(640, LOG_HEIGHT)

class OutputScene(QtOpenGL.QGLWidget):
    def __init__(self, entity, application):
        self._entity = entity
        self._application = application
        self.bvh_reader = entity.bvh_reader
        self._hierarchy = self.bvh_reader.get_hierarchy()
        self._pose = self.bvh_reader.create_pose()
        self.args = application.args
        self._set_camera_from_arg(self.args.camera)
        self._dragging_orientation = False
        self._dragging_y_position = False
        self.width = None
        QtOpenGL.QGLWidget.__init__(self)
        self._previous_frame_index = None
        self.setMouseTracking(True)
        self._floor = FloorCheckerboard(**FLOOR_ARGS)
        self._joint_info = None
            
        self._x_rotation_index = self._hierarchy.get_rotation_index("x")
        self._y_rotation_index = self._hierarchy.get_rotation_index("y")
        self._z_rotation_index = self._hierarchy.get_rotation_index("z")

        self._frame = self._new_frame()

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(1.0 / self.args.frame_rate)
        QtCore.QObject.connect(self._timer, QtCore.SIGNAL('timeout()'), self.updateGL)
        
    def set_enabled(self, enabled):
        self.setVisible(enabled)
        if enabled:
            self._timer.start()
        else:
            self._timer.stop()

    def _new_frame(self):
        return [self._create_empty_joint_data()
                for n in range(self._hierarchy.get_num_joints())]

    def _create_empty_joint_data(self):
        return {}

    def set_pose(self, pose):
        self._process_joint_recurse(pose.get_root_joint())
        self._joint_info = copy.copy(self._frame)

    def _process_joint_recurse(self, joint):
        if not joint.definition.has_parent:
            self._process_joint_translation(joint)
        if joint.definition.has_rotation:
            self._process_joint_orientation(joint)
        for child in joint.children:
            self._process_joint_recurse(child)

    def _process_joint_translation(self, joint):
        self._frame[joint.definition.index].update(
            {"Xposition": joint.worldpos[0],
             "Yposition": joint.worldpos[1],
             "Zposition": joint.worldpos[2]})

    def _process_joint_orientation(self, joint):
        self._frame[joint.definition.index].update(
            {"Xrotation": math.degrees(joint.angles[self._x_rotation_index]),
             "Yrotation": math.degrees(joint.angles[self._y_rotation_index]),
             "Zrotation": math.degrees(joint.angles[self._z_rotation_index])})
        
    def _set_camera_from_arg(self, arg):
        pos_x, pos_y, pos_z, orient_y, orient_z = map(float, arg.split(","))
        self._set_camera_position([pos_x, pos_y, pos_z])
        self._set_camera_orientation(orient_y, orient_z)

    def _set_camera_position(self, position):
        self._camera_position = position

    def _set_camera_orientation(self, y_orientation, x_orientation):
        self._camera_y_orientation = y_orientation
        self._camera_x_orientation = x_orientation

    def key_pressed(self, key):
        r = math.radians(self._camera_y_orientation)
        new_position = self._camera_position
        if key == QtCore.Qt.Key_A:
            new_position[0] += CAMERA_KEY_SPEED * math.cos(r)
            new_position[2] += CAMERA_KEY_SPEED * math.sin(r)
            self._set_camera_position(new_position)
            return
        elif key == QtCore.Qt.Key_D:
            new_position[0] -= CAMERA_KEY_SPEED * math.cos(r)
            new_position[2] -= CAMERA_KEY_SPEED * math.sin(r)
            self._set_camera_position(new_position)
            return
        elif key == QtCore.Qt.Key_W:
            new_position[0] += CAMERA_KEY_SPEED * math.cos(r + math.pi/2)
            new_position[2] += CAMERA_KEY_SPEED * math.sin(r + math.pi/2)
            self._set_camera_position(new_position)
            return
        elif key == QtCore.Qt.Key_S:
            new_position[0] -= CAMERA_KEY_SPEED * math.cos(r + math.pi/2)
            new_position[2] -= CAMERA_KEY_SPEED * math.sin(r + math.pi/2)
            self._set_camera_position(new_position)
            return

    def sizeHint(self):
        return QtCore.QSize(640, 480)

    def initializeGL(self):
        glClearColor(0.0, 0.0, 0.0, 0.0)
        glClearAccum(0.0, 0.0, 0.0, 0.0)
        glClearDepth(1.0)
        glShadeModel(GL_SMOOTH)
        glEnable(GL_LINE_SMOOTH)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glutInit(sys.argv)

    def resizeGL(self, window_width, window_height):
        self.window_width = window_width
        self.window_height = window_height
        if window_height == 0:
            window_height = 1
        glViewport(0, 0, window_width, window_height)
        self.margin = 0
        self.width = window_width - 2*self.margin
        self.height = window_height - 2*self.margin
        self._aspect_ratio = float(window_width) / window_height
        self.min_dimension = min(self.width, self.height)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(self.margin, self.margin, 0)
        self.render()

    def configure_3d_projection(self, pixdx=0, pixdy=0):
        self.fovy = 45
        self.near = 0.1
        self.far = 100.0

        fov2 = ((self.fovy*math.pi) / 180.0) / 2.0
        top = self.near * math.tan(fov2)
        bottom = -top
        right = top * self._aspect_ratio
        left = -right
        xwsize = right - left
        ywsize = top - bottom
        dx = -(pixdx*xwsize/self.width)
        dy = -(pixdy*ywsize/self.height)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glFrustum (left + dx, right + dx, bottom + dy, top + dy, self.near, self.far)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        glRotatef(self._camera_x_orientation, 1.0, 0.0, 0.0)
        glRotatef(self._camera_y_orientation, 0.0, 1.0, 0.0)
        glTranslatef(*self._camera_position)

    def render(self):
        self.configure_3d_projection(-100, 0)
        camera_x = self._camera_position[0]
        camera_z = self._camera_position[2]
        self._floor.render(0, 0, camera_x, camera_z)
        if self._joint_info is not None:
            self._hierarchy.set_pose_from_joint_dicts(self._pose, self._joint_info)
            self._render_pose(self._pose)
                
    def _render_pose(self, pose):
        glColor3f(1, 1, 1)
        glLineWidth(5.0)
        self._render_joint(pose.get_root_joint())
        
    def _render_joint(self, joint):
        for child in joint.children:
            v1 = self.bvh_reader.normalize_vector_without_translation(joint.worldpos)
            v2 = self.bvh_reader.normalize_vector_without_translation(child.worldpos)
            self._render_edge(v1, v2)
            self._render_joint(child)

    def _render_edge(self, v1, v2):
        glBegin(GL_LINES)
        self._vertex(v1)
        self._vertex(v2)
        glEnd()

    def _vertex(self, worldpos):
        if self._application.z_up:
            glVertex3f(worldpos[0], worldpos[2], worldpos[1])
        else:
            glVertex3f(worldpos[0], worldpos[1], worldpos[2])

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._dragging_orientation = True
        elif event.button() == QtCore.Qt.RightButton:
            self._dragging_y_position = True

    def mouseReleaseEvent(self, event):
        self._dragging_orientation = False
        self._dragging_y_position = False
        self._drag_x_previous = event.x()
        self._drag_y_previous = event.y()

    def mouseMoveEvent(self, event):
        x = event.x()
        y = event.y()
        if self._dragging_orientation:
            self._set_camera_orientation(
                self._camera_y_orientation + CAMERA_DRAG_SPEED * (x - self._drag_x_previous),
                self._camera_x_orientation + CAMERA_DRAG_SPEED * (y - self._drag_y_previous))
        elif self._dragging_y_position:
            self._camera_position[1] += CAMERA_Y_SPEED * (y - self._drag_y_previous)
        self._drag_x_previous = x
        self._drag_y_previous = y

    def print_camera_settings(self):
        print "%.3f,%.3f,%.3f,%.3f,%.3f" % (
            self._camera_position[0],
            self._camera_position[1],
            self._camera_position[2],
            self._camera_y_orientation, self._camera_x_orientation)
        
def set_up_logging():
    logging.basicConfig(
        format="%(asctime)s %(name)-20s %(levelname)-8s %(message)s",
        level=logging.DEBUG,
        filename="logs/application.log",
        filemode="w")
