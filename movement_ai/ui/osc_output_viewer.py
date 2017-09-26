import math
import copy
from argparse import ArgumentParser
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from PyQt4 import QtCore, QtGui, QtOpenGL
from collections import defaultdict
import numpy

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")
from bvh import bvh_reader as bvh_reader_module
from connectivity.simple_osc_receiver import OscReceiver
from floor_checkerboard import FloorCheckerboard
from ui.window import Window

FLOOR_ARGS = {"num_cells": 26, "size": 26,
              "board_color1": (.2, .2, .2, 1),
              "board_color2": (.3, .3, .3, 1),
              "floor_color": None,
              "background_color": (0.0, 0.0, 0.0, 0.0)}
CAMERA_Y_SPEED = .01
CAMERA_KEY_SPEED = .1
CAMERA_DRAG_SPEED = .1
FRAME_RATE = 50
ORIGIN_SIZE = 1

class Avatar:
    def __init__(self):
        self.pose = bvh_reader.create_pose()
        self.frame = None
        self.is_renderable = False

class MainWindow(Window):
    def __init__(self, bvh_reader, args):
        Window.__init__(self, args)
        self._layout = QtGui.QVBoxLayout()
        self._layout.setSpacing(0)
        self._layout.setMargin(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._scene = Scene(bvh_reader, args)
        self._layout.addWidget(self._scene)
        self._create_menu()
        self.setLayout(self._layout)
        
        if args.fullscreen:
            self.give_keyboard_focus_to_fullscreen_window()
            self._fullscreen_action.toggle()

    def _create_menu(self):
        self._menu_bar = QtGui.QMenuBar()
        self._layout.setMenuBar(self._menu_bar)
        self._create_main_menu()
        self._create_view_menu()

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

    def _create_view_menu(self):
        self._view_menu = self._menu_bar.addMenu("View")
        self._add_origin_action()
        self._add_fullscreen_action()

    def _add_origin_action(self):
        self._origin_action = QtGui.QAction('Origin', self)
        self._origin_action.setCheckable(True)
        self._origin_action.setShortcut('o')
        self._origin_action.toggled.connect(self._toggled_origin)
        self._view_menu.addAction(self._origin_action)

    def _toggled_origin(self):
        self._scene.view_origin = self._origin_action.isChecked()
        
    def _add_fullscreen_action(self):
        self._fullscreen_action = QtGui.QAction('Fullscreen', self)
        self._fullscreen_action.setCheckable(True)
        self._fullscreen_action.setShortcut('Ctrl+Return')
        self._fullscreen_action.toggled.connect(self._toggled_fullscreen)
        self._view_menu.addAction(self._fullscreen_action)

    def _toggled_fullscreen(self):
        if self._fullscreen_action.isChecked():
            self.enter_fullscreen()
        else:
            self.leave_fullscreen()
            
    def keyPressEvent(self, event):
        self._scene.keyPressEvent(event)
        QtGui.QWidget.keyPressEvent(self, event)
        
class Scene(QtOpenGL.QGLWidget):
    def __init__(self, bvh_reader, args):
        self.bvh_reader = bvh_reader
        self._hierarchy = bvh_reader.get_hierarchy()
        self._avatars = {}
        self.args = args
        self.margin = 0
        self._set_camera_from_arg(args.camera)
        self._current_avatar = None
        self._dragging_orientation = False
        self._dragging_y_position = False
        self.view_origin = False
        QtOpenGL.QGLWidget.__init__(self)
        self.setMouseTracking(True)
        if args.enable_floor:
            self._floor = FloorCheckerboard(**FLOOR_ARGS)

        self._osc_receiver = OscReceiver(args.port)
        self._osc_receiver.add_method("/avatar_begin", "i", self._handle_avatar_begin)
        self._osc_receiver.add_method("/avatar_end", "", self._handle_avatar_end)
        if self.args.type == "bvh":
            self._osc_receiver.add_method("/translation", "iifff", self._handle_translation)
            self._osc_receiver.add_method("/orientation", "iifff", self._handle_orientation)
        elif self.args.type == "world":
            self._osc_receiver.add_method("/world", "iifff", self._handle_world)
        self._osc_receiver.start(auto_serve=True)

        self._x_rotation_index = self._hierarchy.get_rotation_index("x")
        self._y_rotation_index = self._hierarchy.get_rotation_index("y")
        self._z_rotation_index = self._hierarchy.get_rotation_index("z")
        
        timer = QtCore.QTimer(self)
        timer.setInterval(1000. / FRAME_RATE)
        QtCore.QObject.connect(timer, QtCore.SIGNAL('timeout()'), self.updateGL)
        timer.start()

    def _new_frame(self):
        return [self._create_empty_joint_data()
                for n in range(self._hierarchy.get_num_joints())]

    def _create_empty_joint_data(self):
        if self.args.type == "bvh":
            return {}
        elif self.args.type == "world":
            return None

    def _handle_avatar_begin(self, path, args, types, src, user_data):
        index = args[0]
        if index not in self._avatars:
            self._avatars[index] = Avatar()
        self._current_avatar = self._avatars[index]
        self._current_avatar.frame = self._new_frame()

    def _handle_avatar_end(self, path, args, types, src, user_data):
        if self._current_avatar is None:
            return
        if self.args.type == "world":
            self._current_avatar.vertices = copy.copy(self._current_avatar.frame)
        elif self.args.type == "bvh":
            self._current_avatar.joint_info = copy.copy(self._current_avatar.frame)
        self._current_avatar.is_renderable = True
        self._current_avatar.frame = None
        self._current_avatar = None
        
    def _handle_world(self, path, args, types, src, user_data):
        if self._current_avatar is None:
            return
        frame_count, joint_index, x, y, z = args
        self._current_avatar.frame[joint_index] = (x, y, z)

    def _handle_translation(self, path, args, types, src, user_data):
        if self._current_avatar is None:
            return
        frame_count, joint_index, x, y, z = args
        self._current_avatar.frame[joint_index].update(
            {"Xposition": x,
             "Yposition": y,
             "Zposition": z})

    def _handle_orientation(self, path, args, types, src, user_data):
        if self._current_avatar is None:
            return
        frame_count, joint_index, angle0, angle1, angle2 = args
        angles = [angle0, angle1, angle2]
        self._current_avatar.frame[joint_index].update(
            {"Xrotation": math.degrees(angles[self._x_rotation_index]),
             "Yrotation": math.degrees(angles[self._y_rotation_index]),
             "Zrotation": math.degrees(angles[self._z_rotation_index])})
             
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
        camera_x = self._camera_position[0]
        camera_z = self._camera_position[2]
        if args.enable_floor:
            self._floor.render(0, 0, camera_x, camera_z)
        if self.view_origin:
            self._render_origin()
        for avatar in self._avatars.values():
            if avatar.is_renderable:
                self._render_avatar(avatar)

    def _render_origin(self):
        glLineWidth(1.0)
        self._draw_colored_line((1,0,0))
        self._draw_colored_line((0,1,0))
        self._draw_colored_line((0,0,1))

    def _draw_colored_line(self, triple):
        glColor3f(*triple)
        glBegin(GL_LINES)
        glVertex3f(0,0,0)
        glVertex3f(*(numpy.array(triple)*ORIGIN_SIZE))
        glEnd()
        
    def _render_avatar(self, avatar):
        glColor3f(1, 1, 1)
        glLineWidth(5.0)
        if self.args.type == "bvh":
            self._hierarchy.set_pose_from_joint_dicts(avatar.pose, avatar.joint_info)
            self._render_pose(avatar.pose)
        elif self.args.type == "world":
            edges = self.bvh_reader.vertices_to_edges(avatar.vertices)
            for edge in edges:
                self._render_edge(edge.v1, edge.v2)
                
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
        if self.args.z_up:
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
        
parser = ArgumentParser()
Window.add_parser_arguments(parser)
parser.add_argument("bvh", type=str)
parser.add_argument("--camera", help="posX,posY,posZ,orientY,orientX",
                    default="-3.767,-1.400,-3.485,-55.500,18.500")
parser.add_argument("--port", type=int, default=10000)
parser.add_argument("--z-up", action="store_true")
parser.add_argument("--type", choices=["bvh", "world"], default="bvh")
parser.add_argument("--enable-floor", action="store_true")
args = parser.parse_args()

bvh_reader = bvh_reader_module.BvhReader(args.bvh)
bvh_reader.read()

app = QtGui.QApplication(sys.argv)
window = MainWindow(bvh_reader, args)
window.show()
app.exec_()
