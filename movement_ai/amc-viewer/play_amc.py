#!/usr/bin/perl

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")

import cgkit.asfamc
import window
from argparse import ArgumentParser
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import threading

class AmcViewer(window.Window):
    def __init__(self, *args):
        global amc_reader
        window.Window.__init__(self, *args)
        self.reader = amc_reader

    def render(self):
        self.configure_3d_projection(100, 0)
        self._draw_unit_cube()
        self._draw_points()

    def _draw_unit_cube(self):
        glColor4f(0,0,0,0.2)
        glutWireCube(2.0)

    def _draw_points(self):
        if len(self.reader.frames) > 0:
            glPointSize(2.0)
            glBegin(GL_POINTS)
            for joint, point in self.reader.frames[0]:
                if len(point) == 3:
                    glVertex3f(*point)
            glEnd()

class AsfReader(cgkit.asfamc.ASFReader):
    def __init__(self, *args):
        cgkit.asfamc.ASFReader.__init__(self, *args)

    def onRoot(self, root):
        print(root)
    # def onBonedata(self, bones):
    #     print bones

class AmcReader(cgkit.asfamc.AMCReader):
    def __init__(self, *args):
        cgkit.asfamc.AMCReader.__init__(self, *args)
        self.frames = []

    def onFrame(self, framenr, data):
        self.frames.append(data)

parser = ArgumentParser()
window.Window.add_parser_arguments(parser)
parser.add_argument("-amc")
parser.add_argument("-asf")
args = parser.parse_args()

asf_reader = AsfReader(args.asf)
asf_reader.read()

amc_reader = AmcReader(args.amc)
amc_reader_thread = threading.Thread(target=amc_reader.read)
amc_reader_thread.daemon = True
amc_reader_thread.start()

window.run(AmcViewer, args)
