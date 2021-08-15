#!/usr/bin/env python

STUDENT_MODEL_PATH = "profiles/dimensionality_reduction/valencia_pn_autoencoder_2d.model"
SKELETON_DEFINITION = "scenes/pn-01.22_skeleton.bvh"
DIMENSIONALITY_REDUCTION_TYPE = "AutoEncoder"
DIMENSIONALITY_REDUCTION_ARGS = "--num-hidden-nodes=0 --learning-rate=0.006 --tied-weights"
ENTITY_ARGS = "-r quaternion"

NUM_REDUCED_DIMENSIONS = 2
Z_UP = False
FLOOR = True

FRAME_RATE = 50

from argparse import ArgumentParser
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from PyQt4 import QtCore, QtGui, QtOpenGL
import numpy
import collections
import threading

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")
from entities.hierarchical import Entity
from bvh.bvh_reader import BvhReader
from dimensionality_reduction.factory import DimensionalityReductionFactory
import tracking.pn.receiver

parser = ArgumentParser()
Entity.add_parser_arguments(parser)
parser.add_argument("--pn-host", default="localhost")
parser.add_argument("--pn-port", type=int, default=tracking.pn.receiver.SERVER_PORT_BVH)
parser.add_argument("--grid-resolution", type=int, default=5)
parser.add_argument("--explore-beyond-observations", type=float, default=0.2)
parser.add_argument("--memory-size", type=int, default=1000)
args = parser.parse_args()

bvh_reader = BvhReader(SKELETON_DEFINITION)
bvh_reader.read()
entity_args_strings = ENTITY_ARGS.split()
entity_args = parser.parse_args(entity_args_strings)

pose = bvh_reader.get_hierarchy().create_pose()
entity = Entity(bvh_reader, pose, FLOOR, Z_UP, entity_args)

num_input_dimensions = entity.get_value_length()
student = DimensionalityReductionFactory.create(
    DIMENSIONALITY_REDUCTION_TYPE, num_input_dimensions, NUM_REDUCED_DIMENSIONS, DIMENSIONALITY_REDUCTION_ARGS)
student.load(STUDENT_MODEL_PATH)

training_data = collections.deque([], maxlen=args.memory_size)
input_from_pn = None

class MainWindow(QtOpenGL.QGLWidget):
    def __init__(self):
        super(MainWindow, self).__init__()
        self._explored_range = 1.0 + args.explore_beyond_observations
        self._explored_min = .5 - self._explored_range/2
        self._explored_max = .5 + self._explored_range/2
        
        timer = QtCore.QTimer(self)
        timer.setInterval(1000. / FRAME_RATE)
        QtCore.QObject.connect(timer, QtCore.SIGNAL('timeout()'), self.updateGL)
        timer.start()

    def sizeHint(self):
        return QtCore.QSize(800, 800)

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
        global input_from_pn
        if input_from_pn is None:
            return
        
        student.train([input_from_pn])
        training_data.append(input_from_pn)
        student.probe(training_data)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(self.margin, self.margin, 0)
        
        self.configure_2d_projection(0, self.width, 0, self.height)
        
        self._render_input(input_from_pn)
        
        glColor3f(1,1,1)
        for grid_y in range(args.grid_resolution):
            for grid_x in range(args.grid_resolution):
                self._render_cell(grid_x, grid_y)

    def _render_input(self, input_):
        vertices = entity.process_input(input_)
        glColor3f(.5, .5, .5)
        self._render_vertices_2d(
            vertices,
            x_offset=0.5,
            y_offset=0.8,
            scale=0.5)
    
    def configure_2d_projection(self, left, right, bottom, top):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(left, right, bottom, top, -1.0, 1.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        self._eye = (self.width/2, self.height/2, 5000)
        
    def _render_cell(self, grid_x, grid_y):
        normalized_reduction = self._get_normalized_reduction(grid_x, grid_y)

        px = float(grid_x) / args.grid_resolution * self.width
        py = float(grid_y) / args.grid_resolution * self.height
        
        reduction = student.unnormalize_reduction(normalized_reduction)
        output = student.inverse_transform(numpy.array([reduction]))[0]
        vertices = entity.process_output(output)
        
        glPushMatrix()
        glTranslatef(px, py, 0)
        self._render_vertices_2d(
            vertices,
            x_offset=0.1,
            y_offset=0.1,
            scale=1.0/args.grid_resolution)
        glPopMatrix()

    def _get_normalized_reduction(self, grid_x, grid_y):
        normalized_reduction = [0.5] * student.num_reduced_dimensions
        if args.grid_resolution > 1:
            normalized_reduction[0] = float(grid_x) / (args.grid_resolution - 1) \
                                      * self._explored_range + self._explored_min
            normalized_reduction[1] = float(grid_y) / (args.grid_resolution - 1) \
                                      * self._explored_range + self._explored_min
        return normalized_reduction
        
    def _render_vertices_2d(self, vertices, x_offset=0, y_offset=0, scale=1):
        screen_vertices = [
            self._world_to_screen(world_vertex)
            for world_vertex in vertices]
        screen_vertices = self._adjust_screen_vertices(
            screen_vertices,
            x_offset,
            y_offset,
            scale=scale)
        screen_edges = bvh_reader.vertices_to_edges(screen_vertices)
        glLineWidth(2.0)
        for edge in screen_edges:
            self._render_edge_2d(edge.v1, edge.v2)

    def _world_to_screen(self, world):
        x = (self._eye[2] * (world[0]-self._eye[0])) / (self._eye[2] + world[2]) + self._eye[0];
        y = (self._eye[2] * (world[1]-self._eye[1])) / (self._eye[2] + world[2]) + self._eye[1];
        screen = (x, y)
        return screen

    def _adjust_screen_vertices(self, vertices, x_offset, y_offset, scale):
        hip_x = vertices[0][0]
        return [
            ((vertex[0] - hip_x) * scale + x_offset, (vertex[1] + y_offset) * scale)
            for vertex in vertices]

    def _render_edge_2d(self, v1, v2):
        glBegin(GL_LINES)
        glVertex2f(v1[0] * self.width, v1[1] * self.height)
        glVertex2f(v2[0] * self.width, v2[1] * self.height)
        glEnd()    

        
def receive_from_pn(pn_entity):
    global input_from_pn
    for frame in pn_receiver.get_frames():
        input_from_pn = pn_entity.get_value_from_frame(frame)
                
pn_receiver = tracking.pn.receiver.PnReceiver()
print("connecting to PN server...")
pn_receiver.connect(args.pn_host, args.pn_port)
print("ok")
pn_pose = bvh_reader.get_hierarchy().create_pose()
pn_entity = Entity(bvh_reader, pn_pose, FLOOR, Z_UP, entity_args)
pn_receiver_thread = threading.Thread(target=lambda: receive_from_pn(pn_entity))
pn_receiver_thread.daemon = True
pn_receiver_thread.start()

app = QtGui.QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec_()
