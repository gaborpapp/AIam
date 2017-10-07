#!/usr/bin/python

import math
import time
from bvh_collection import BvhCollection
from argparse import ArgumentParser
from PyQt4 import QtCore, QtGui, QtOpenGL
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import glob
import SocketServer
import threading

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")

from ui.window import Window

CAMERA_Y_SPEED = .01
CAMERA_KEY_SPEED = .1
CAMERA_DRAG_SPEED = .1
SLIDER_PRECISION = 1000
FRAME_RATE = 30

class MainWindow(Window):
    def __init__(self, bvh_reader, args):
        global transport_layout
        Window.__init__(self, args)
        self._main_layout = QtGui.QVBoxLayout()
        self._main_layout.setSpacing(0)
        self._main_layout.setMargin(0)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._scene = Scene(bvh_reader, args)
        self._main_layout.addWidget(self._scene)
        transport_layout = TransportLayout()
        self._main_layout.addLayout(transport_layout)
        self._create_menu()
        self.setLayout(self._main_layout)

    def _create_menu(self):
        self._menu_bar = QtGui.QMenuBar()
        self._main_layout.setMenuBar(self._menu_bar)
        self._create_main_menu()

    def _create_main_menu(self):
        self._main_menu = self._menu_bar.addMenu("&Main")
        self._add_show_camera_settings_action()
        self._add_quit_action()
        
    def _add_show_camera_settings_action(self):
        action = QtGui.QAction('Show camera settings', self)
        action.triggered.connect(self._scene.print_camera_settings)
        self._main_menu.addAction(action)
        
    def _add_quit_action(self):
        action = QtGui.QAction("&Quit", self)
        action.triggered.connect(QtGui.QApplication.exit)
        self._main_menu.addAction(action)
        
    def keyPressEvent(self, event):
        self._scene.keyPressEvent(event)
        QtGui.QWidget.keyPressEvent(self, event)

class TransportLayout(QtGui.QHBoxLayout):
    def __init__(self):
        QtGui.QHBoxLayout.__init__(self)
        self._add_cursor_slider()
        self._add_frame_index_label()
        self._add_play_button()
        self._add_stop_button()

    def _add_cursor_slider(self):
        def create_slider():
            slider = QtGui.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, SLIDER_PRECISION)
            slider.setSingleStep(1)
            slider.valueChanged.connect(on_changed_slider_value)
            return slider

        def on_changed_slider_value(slider_value):
            frame_index = int(float(slider_value) / SLIDER_PRECISION * bvh_reader.get_num_frames())
            transport.set_frame_index(frame_index)
            self._update_frame_index_label(frame_index)
            
        self._cursor_slider = create_slider()
        self.addWidget(self._cursor_slider)

    def set_cursor_value(self, frame_index):
        self._cursor_slider.setValue(float(frame_index) / bvh_reader.get_num_frames() * SLIDER_PRECISION)
        self._update_frame_index_label(frame_index)

    def _update_frame_index_label(self, frame_index):
        self._frame_index_label.setText("%d" % frame_index)

    def _add_frame_index_label(self):
        self._frame_index_label = QtGui.QLabel()
        self._frame_index_label.setFixedWidth(60)
        self.addWidget(self._frame_index_label)
        
    def _add_play_button(self):
        button = QtGui.QPushButton(text="Play")
        button.clicked.connect(transport.play)
        self.addWidget(button)

    def _add_stop_button(self):
        button = QtGui.QPushButton(text="Stop")
        button.clicked.connect(transport.stop)
        self.addWidget(button)
        
class Scene(QtOpenGL.QGLWidget):
    def __init__(self, bvh_reader, args):
        self.bvh_reader = bvh_reader
        self.args = args
        self._pose = bvh_reader.get_hierarchy().create_pose()
        self._set_camera_from_arg(args.camera)
        self._dragging_orientation = False
        self._dragging_y_position = False
        self.width = None
        QtOpenGL.QGLWidget.__init__(self)
        self._previous_frame_index = None
        self.setMouseTracking(True)
            
        timer = QtCore.QTimer(self)
        timer.setInterval(1.0 / FRAME_RATE)
        QtCore.QObject.connect(timer, QtCore.SIGNAL('timeout()'), self.updateGL)
        timer.start()
             
    def _set_camera_from_arg(self, arg):
        pos_x, pos_y, pos_z, orient_y, orient_z = map(float, arg.split(","))
        self._set_camera_position([pos_x, pos_y, pos_z])
        self._set_camera_orientation(orient_y, orient_z)

    def _set_camera_position(self, position):
        self._camera_position = position

    def _set_camera_orientation(self, y_orientation, x_orientation):
        self._camera_y_orientation = y_orientation
        self._camera_x_orientation = x_orientation

    def keyPressEvent(self, event):
        r = math.radians(self._camera_y_orientation)
        new_position = self._camera_position
        key = event.key()
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
        return QtCore.QSize(800, 600)

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
        if args.unit_cube:
            self._draw_unit_cube()
        self._draw_skeleton()
        transport.update()
        if transport.is_playing:
            transport_layout.set_cursor_value(transport.frame_index)

    def _draw_skeleton(self):
        global pn_frame_values
        frame_index = transport.frame_index
        if frame_index != self._previous_frame_index:
            if args.simulate_pn:
                pn_frame_values = self.bvh_reader.get_frame_by_index(frame_index)
            self.bvh_reader.set_pose_from_frame_index(self._pose, frame_index)
            self._process_pose_to_edges()
            self._previous_frame_index = frame_index
        self._render_edges()
        
    def _process_pose_to_edges(self):
        self._edges = []
        self._process_joint_to_edges_recurse(self._pose.get_root_joint())
        
    def _process_joint_to_edges_recurse(self, joint):
        for child in joint.children:
            v1 = self.bvh_reader.normalize_vector_without_translation(joint.worldpos)
            v2 = self.bvh_reader.normalize_vector_without_translation(child.worldpos)
            self._edges.append((v1, v2))
            self._process_joint_to_edges_recurse(child)

    def _render_edges(self):
        glColor3f(1, 1, 1)
        glLineWidth(5.0)
        for v1, v2 in self._edges:
            glBegin(GL_LINES)
            self._vertex(v1)
            self._vertex(v2)
            glEnd()

    def _vertex(self, worldpos):
        if self.args.z_up:
            glVertex3f(worldpos[0], worldpos[2], worldpos[1])
        else:
            glVertex3f(worldpos[0], worldpos[1], worldpos[2])

    def _draw_unit_cube(self):
        glColor4f(1,1,1,0.2)
        glutWireCube(2.0)

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

class Transport:
    def __init__(self, num_frames, duration, frame_rate):
        self._num_frames = num_frames
        self._duration = duration
        self._frame_rate = frame_rate
        self._frame_index = 0
        self._time = 0
        self._is_playing = False

    @property
    def frame_index(self):
        return self._frame_index

    @property
    def is_playing(self):
        return self._is_playing
    
    def rewind(self):
        self.set_time(0)

    def set_time(self, t):
        self._time = t
        self.set_frame_index(int(self._time * self._frame_rate))

    def play(self):
        self._is_playing = True
        self._play_start_time = time.time()
        self._play_time_offset = self._time

    def stop(self):
        self._is_playing = False

    def update(self):
        now = time.time()
        if self._is_playing:
            self.set_time(self._play_time_offset + now - self._play_start_time)
            if self._time >= self._duration:
                if args.loop:
                    self.rewind()
                else:
                    self.set_frame_index(self._num_frames - 1)
                    self.stop()

    def set_frame_index(self, value):
        self._frame_index = min(value, self._num_frames - 1)
        if not self._is_playing:
            self._time = float(self._frame_index) / self._frame_rate

parser = ArgumentParser()
Window.add_parser_arguments(parser)
parser.add_argument("-bvh")
parser.add_argument("--camera", help="posX,posY,posZ,orientY,orientX",
                    default="-3.767,-1.400,-3.485,-71.900,4.800")
parser.add_argument("-speed", type=float, default=1.0)
parser.add_argument("-zoom", type=float, default=1.0)
parser.add_argument("-unit-cube", action="store_true")
parser.add_argument("-loop", action="store_true")
parser.add_argument("-vertex-size", type=float, default=0)
parser.add_argument("--z-up", action="store_true")
parser.add_argument("--simulate-pn", action="store_true")
parser.add_argument("--pn-port", default=7002)
args = parser.parse_args()

bvh_filenames = glob.glob(args.bvh)
bvh_reader = BvhCollection(bvh_filenames)
bvh_reader.read()

frame_rate = 1.0 / bvh_reader.get_frame_time()
transport = Transport(
    bvh_reader.get_num_frames(),
    bvh_reader.get_duration(),
    frame_rate)

if args.simulate_pn:
    class PnSimulatorHandler(SocketServer.BaseRequestHandler):
        def handle(self):
            global pn_frame_values

            sending_start_time = time.time()
            num_frames_sent = 0
            while True:
                if num_frames_sent > 0:
                    sending_fps = float(num_frames_sent) / (time.time() - sending_start_time)
                    if sending_fps > frame_rate:
                        time.sleep(0.00001)
                        continue

                if pn_frame_values is not None:
                    string = "mock_ID mock_name"
                    for value in pn_frame_values:
                        string += " "
                        string += str(value)
                    string += "||\n"
                    self.request.sendall(string)

                num_frames_sent += 1

    class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
        pass

    pn_frame = None
    server = ThreadedTCPServer(("localhost", args.pn_port), PnSimulatorHandler)
    server.allow_reuse_address = True
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

app = QtGui.QApplication(sys.argv)
window = MainWindow(bvh_reader, args)
transport_layout.set_cursor_value(0)
window.show()
app.exec_()
