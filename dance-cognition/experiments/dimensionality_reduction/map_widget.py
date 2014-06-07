from experiment import *

SPLIT_SENSITIVITY = .2

class MapTab(QtGui.QWidget):
    def __init__(self, parent, map_dimensions):
        QtGui.QWidget.__init__(self)
        self._map_dimensions = map_dimensions
        self._parent = parent
        self.experiment = parent.experiment
        self._map_layout = QtGui.QVBoxLayout()
        self._add_map_dimension_checkboxes()
        self._add_map_widget()
        self._map_layout.addStretch(1)
        self.setLayout(self._map_layout)

    def set_path(self, path):
        self._map_widget.set_path(path)

    def set_reduction(self, reduction):
        self._map_widget.set_reduction(reduction)

    def reduction_changed(self, reduction):
        self._map_widget.set_reduction(reduction)
        self._map_widget.updateGL()

    def _add_map_widget(self):
        self._map_widget = MapWidget(self._parent, self._map_dimensions)
        self._map_widget.setFixedSize(370, 370)
        self._map_layout.addWidget(self._map_widget)

    def _add_map_dimension_checkboxes(self):
        layout = QtGui.QHBoxLayout()
        self._map_dimension_checkboxes = []
        for n in range(self.experiment.student.n_components):
            checkbox = QtGui.QCheckBox()
            if n in self._map_dimensions:
                checkbox.setCheckState(QtCore.Qt.Checked)
            checkbox.stateChanged.connect(self._map_dimensions_changed)
            self._map_dimension_checkboxes.append(checkbox)
            layout.addWidget(checkbox)
        self._map_layout.addLayout(layout)

    def _map_dimensions_changed(self):
        checked_dimensions = filter(
            lambda n: self._map_dimension_checkboxes[n].checkState() == QtCore.Qt.Checked,
            range(self.experiment.student.n_components))
        if len(checked_dimensions) == 2:
            self._map_widget.set_dimensions(checked_dimensions)

class MapWidget(QtOpenGL.QGLWidget):
    def __init__(self, parent, dimensions):
        self.experiment = parent.experiment
        self.set_dimensions(dimensions)
        QtOpenGL.QGLWidget.__init__(self, parent)

    def set_dimensions(self, dimensions):
        self._dimensions = dimensions
        observations = self.experiment.student.normalized_observed_reductions[
            :,dimensions]
        self._split_into_segments(observations)
        self._reduction = None
        self._path = None

    def _split_into_segments(self, observations):
        self._segments = []
        segment = []
        previous_observation = None
        for observation in observations:
            if previous_observation is not None and \
                    numpy.linalg.norm(observation - previous_observation) > SPLIT_SENSITIVITY:
                self._segments.append(segment)
                segment = []
            segment.append(observation)
            previous_observation = observation
        if len(segment) > 0:
            self._segments.append(segment)

    def set_reduction(self, reduction):
        self._reduction = reduction[self._dimensions]

    def set_path(self, path):
        self._path = path[:,self._dimensions]

    def initializeGL(self):
        glClearColor(1.0, 1.0, 1.0, 0.0)
        glClearAccum(0.0, 0.0, 0.0, 0.0)
        glEnable(GL_LINE_SMOOTH)
        glEnable(GL_POINT_SMOOTH)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def resizeGL(self, window_width, window_height):
        self.window_width = window_width
        self.window_height = window_height
        if window_height == 0:
            window_height = 1
        self._margin = 5
        self._width = window_width - 2*self._margin
        self._height = window_height - 2*self._margin
        glViewport(0, 0, window_width, window_height)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glOrtho(0.0, self.window_width, self.window_height, 0.0, -1.0, 1.0)
        glMatrixMode(GL_MODELVIEW)
        glTranslatef(self._margin, self._margin, 0)
        self._render_observations()
        if self._path is not None:
            self._render_path()
        if self._reduction is not None:
            self._render_reduction()

    def _render_observations(self):
        glColor4f(0, 0, 0, .1)
        glLineWidth(1.0)
        for segment in self._segments:
            self._render_segment(segment)

    def _render_segment(self, segment):
        glBegin(GL_LINE_STRIP)
        for x,y in segment:
            glVertex2f(*self._vertex(x, y))
        glEnd()

    def _render_reduction(self):
        glColor3f(0, 0, 0)
        glPointSize(4.0)
        glBegin(GL_POINTS)
        glVertex2f(*self._vertex(*self._reduction))
        glEnd()

    def _render_path(self):
        glPushAttrib(GL_ENABLE_BIT)
        glLineStipple(4, 0xAAAA)
        glEnable(GL_LINE_STIPPLE)
        glColor4f(0, 0, 0, .6)
        glLineWidth(2.0)
        self._render_segment(self._path)
        glPopAttrib()

    def _vertex(self, x, y):
        return x*self._width, y*self._height
