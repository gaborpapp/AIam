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

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")

from ui.window import Window

CAMERA_Y_SPEED = .01
CAMERA_KEY_SPEED = .1
CAMERA_DRAG_SPEED = .1
FRAME_RATE = 50

class MainWindow(Window):
    def __init__(self, bvh_reader, args):
        Window.__init__(self, args)
        self._layout = QtGui.QVBoxLayout()
        self._layout.setSpacing(0)
        self._layout.setMargin(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._scene = Scene(bvh_reader, args)
        self._layout.addWidget(self._scene)
        self.setLayout(self._layout)
        
    def keyPressEvent(self, event):
        self._scene.keyPressEvent(event)
        QtGui.QWidget.keyPressEvent(self, event)

class Scene(QtOpenGL.QGLWidget):
    def __init__(self, bvh_reader, args):
        self.bvh_reader = bvh_reader
        self.args = args
        self._pose = bvh_reader.get_hierarchy().create_pose()
        self._start_time = time.time()
        self._set_camera_from_arg(args.camera)
        self._dragging_orientation = False
        self._dragging_y_position = False
        QtOpenGL.QGLWidget.__init__(self)
        self.setMouseTracking(True)
            
        timer = QtCore.QTimer(self)
        timer.setInterval(1000. / FRAME_RATE)
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

    def _draw_skeleton(self):
        t = (time.time() - self._start_time) * args.speed
        if t > self.bvh_reader.get_duration() and not args.loop:
            return
        self.bvh_reader.set_pose_from_time(self._pose, t)
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

    def keyPressed(self, key, x, y):
        if key == 'r':
            self._rewind()
        else:
            window.Window.keyPressed(self, key, x, y)

    def _rewind(self):
        self.t = 0

parser = ArgumentParser()
Window.add_parser_arguments(parser)
parser.add_argument("-bvh")
parser.add_argument("--camera", help="posX,posY,posZ,orientY,orientX",
                    default="-3.767,-1.400,-3.485,-55.500,18.500")
parser.add_argument("-speed", type=float, default=1.0)
parser.add_argument("-zoom", type=float, default=1.0)
parser.add_argument("-unit-cube", action="store_true")
parser.add_argument("-loop", action="store_true")
parser.add_argument("-vertex-size", type=float, default=0)
parser.add_argument("--z-up", action="store_true")
args = parser.parse_args()

bvh_filenames = glob.glob(args.bvh)
bvh_reader = BvhCollection(bvh_filenames)
bvh_reader.read()

if args.z_up:
    bvh_coordinate_left = 0
    bvh_coordinate_up = 2
    bvh_coordinate_far = 1
else:
    bvh_coordinate_left = 0
    bvh_coordinate_up = 1
    bvh_coordinate_far = 2

app = QtGui.QApplication(sys.argv)
window = MainWindow(bvh_reader, args)
window.show()
app.exec_()
