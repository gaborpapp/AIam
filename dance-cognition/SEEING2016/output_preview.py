import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")

from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from PyQt4 import QtCore, QtGui, QtOpenGL
from dimensionality_reduction.dimensionality_reduction_experiment import *

FRAME_RATE = 50

parser = ArgumentParser()
parser.add_argument("--split-sensitivity", type=float, default=0.2)
parser.add_argument("--dimensions", help="e.g. 0,3 (x as 1st dimension and y as 4th)")

class MapView(QtOpenGL.QGLWidget):
    def __init__(self, parent, experiment):
        QtOpenGL.QGLWidget.__init__(self, parent)
        self._experiment = experiment

    def render(self):
        self._render_map()
        self._render_segments()

    def _render_map(self):
        glColor3f(1, 1, 1)
        glPointSize(3.0)
        glBegin(GL_POINTS)
        for point in self.parent().map_points:
            glVertex2f(*self._vertex(point))
        glEnd()

    def _vertex(self, point):
        x = point[self.parent().dimensions[0]]
        y = point[self.parent().dimensions[1]]
        return x*self.width, y*self.height
        
    def _render_segments(self):
        glColor3f(.7, .7, .7)
        glLineWidth(1.0)
        for segment in self.parent().segments:
            self._render_segment(segment)

    def _render_segment(self, segment):
        glBegin(GL_LINE_STRIP)
        for point in segment:
            glVertex2f(*self._vertex(point))
        glEnd()

    def initializeGL(self):
        glClearColor(0.0, 0.0, 0.0, 0.0)
        glClearAccum(0.0, 0.0, 0.0, 0.0)
        glClearDepth(1.0)
        glEnable(GL_POINT_SMOOTH)
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
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0.0, self.window_width, self.window_height, 0.0, -1.0, 1.0)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(self.margin, self.margin, 0)
        self.render()

    def sizeHint(self):
        return QtCore.QSize(500, 500)

class MainWindow(QtGui.QWidget):
    def __init__(self, experiment):
        self._experiment = experiment
        self.map_points = experiment.student.normalized_observed_reductions
        self.segments = self._get_segments_from_bvhs()
        if experiment.args.split_sensitivity:
            self.segments = self._split_segments_by_sensitivity(self.segments)

        if experiment.args.dimensions:
            self.dimensions = [int(string) for string in experiment.args.dimensions.split(",")]
        else:
            self.dimensions = [0, 1]

        QtGui.QMainWindow.__init__(self)
        self._layout = QtGui.QVBoxLayout()
        self._layout.setSpacing(0)
        self._layout.setMargin(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)
        self._add_map_view()

        timer = QtCore.QTimer(self)
        timer.setInterval(1000. / FRAME_RATE)
        QtCore.QObject.connect(timer, QtCore.SIGNAL('timeout()'), self._update)
        timer.start()

    def _get_segments_from_bvhs(self):
        return [self._get_observations_from_bvh(bvh_reader)
                for bvh_reader in self._experiment.bvh_reader.get_readers()]

    def _get_observations_from_bvh(self, bvh_reader):
        return self._experiment.student.normalized_observed_reductions[
            bvh_reader.start_index : bvh_reader.end_index]

    def _split_segments_by_sensitivity(self, segments):
        result = []
        for observations in segments:
            result += self._split_observations_by_sensitivity(observations)
        return result

    def _split_observations_by_sensitivity(self, observations):
        segments = []
        segment = []
        previous_observation = None
        for observation in observations:
            if previous_observation is not None and \
                    numpy.linalg.norm(observation - previous_observation) > \
                    self._experiment.args.split_sensitivity:
                segments.append(segment)
                segment = []
            segment.append(observation)
            previous_observation = observation
        if len(segment) > 0:
            segments.append(segment)
        return segments

    def _add_map_view(self):
        self._map_view = MapView(self, experiment)
        self._layout.addWidget(self._map_view)

    def _update(self):
        self._map_view.updateGL()

DimensionalityReductionExperiment.add_parser_arguments(parser)
experiment = DimensionalityReductionExperiment(parser)
experiment._load_model()

app = QtGui.QApplication(sys.argv)
window = MainWindow(experiment)
window.show()
app.exec_()
