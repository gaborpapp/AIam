from .dimensionality_reduction_ui import *
from event import merge_event_handler_dicts

SPLIT_SENSITIVITY = .2

class MapTab(ReductionTab, QtWidgets.QWidget):
    def __init__(self, parent, dimensions, normalized_observed_reductions):
        ReductionTab.__init__(self, parent)
        QtWidgets.QWidget.__init__(self)
        self.student = parent.parent().student
        self._dimensions = dimensions
        self._map_layout = QtWidgets.QVBoxLayout()
        self._add_map_dimension_checkboxes()
        self._add_map_widget(normalized_observed_reductions)
        self._map_layout.addStretch(1)
        self.setLayout(self._map_layout)

    def get_event_handlers(self):
        return self._map_widget.get_event_handlers()

    def set_path(self, path):
        self._map_widget.set_path(path)

    def get_normalized_reduction(self):
        return self._map_widget.get_reduction()

    def reduction_changed(self, reduction):
        self._reduction = reduction
        self._map_widget.set_reduction(reduction)

    def set_enabled(self, enabled):
        self._map_widget.set_enabled(enabled)

    def _add_map_widget(self, normalized_observed_reductions):
        self._map_widget = MapWidget(self, self._dimensions, normalized_observed_reductions)
        self._map_widget.setFixedSize(270, 270)
        self._map_layout.addWidget(self._map_widget)

    def _add_map_dimension_checkboxes(self):
        layout = QtWidgets.QHBoxLayout()
        self._map_dimension_checkboxes = []
        for n in range(self.student.num_reduced_dimensions):
            checkbox = QtWidgets.QCheckBox()
            if n in self._dimensions:
                checkbox.setCheckState(QtCore.Qt.Checked)
            checkbox.stateChanged.connect(self._updated_dimensions)
            self._map_dimension_checkboxes.append(checkbox)
            layout.addWidget(checkbox)
        self._map_layout.addLayout(layout)

    def _updated_dimensions(self):
        checked_dimensions = [n for n in range(self.student.num_reduced_dimensions) if self._map_dimension_checkboxes[n].checkState() == QtCore.Qt.Checked]
        if len(checked_dimensions) == 2:
            self._map_widget.updated_dimensions(checked_dimensions)
            self._map_widget.set_reduction(self._reduction)

    def reduction_changed_interactively(self):
        self._reduction = self._map_widget.get_reduction()
        self._parent.reduction_changed_interactively(self)

    def update_qgl_widgets(self):
        self._map_widget.updateGL()

    def set_normalized_observed_reductions(self, normalized_observed_reductions):
        self._map_widget.set_normalized_observed_reductions(normalized_observed_reductions)

class MapWidget(QtOpenGL.QGLWidget):
    def __init__(self, parent, dimensions, normalized_observed_reductions):
        QtOpenGL.QGLWidget.__init__(self, parent)
        self._parent = parent
        self.student = parent.student
        self.normalized_observed_reductions = normalized_observed_reductions
        self._observations_layer = Layer(self._render_observations)
        self.set_dimensions(dimensions)
        self._dragging = False
        self._enabled = False
        self._mode_specific_renderers = {
            modes.IMITATE: ImitateMapViewRenderer(self),
            modes.IMPROVISE: ImproviseMapViewRenderer(self),
            modes.FLANEUR: FlaneurMapViewRenderer(self),
            modes.HYBRID: HybridMapViewRenderer(self),
            }

    def get_event_handlers(self):
        return merge_event_handler_dicts([
                renderer.get_event_handlers()
                for renderer in list(self._mode_specific_renderers.values())])

    def updated_dimensions(self, dimensions):
        self.set_dimensions(dimensions)
        mode_specific_renderer = self._get_mode_specific_renderer()
        if mode_specific_renderer is not None:
            mode_specific_renderer.updated_dimensions()

    def set_dimensions(self, dimensions):
        self.dimensions = dimensions
        self._reduction = None
        self._update_observations_layer()

    def _update_observations_layer(self):
        observations = self.normalized_observed_reductions[:,self.dimensions]
        self._split_into_segments(observations)
        self._observations_layer.refresh()

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

    def set_normalized_observed_reductions(self, normalized_observed_reductions):
        self.normalized_observed_reductions = normalized_observed_reductions
        self._update_observations_layer()
        mode_specific_renderer = self._get_mode_specific_renderer()
        if mode_specific_renderer is not None:
            mode_specific_renderer.updated_normalized_observed_reductions()
        
    def set_reduction(self, reduction_all_dimensions):
        self._reduction_all_dimensions = reduction_all_dimensions
        self._reduction = reduction_all_dimensions[self.dimensions]

    def set_enabled(self, enabled):
        self._enabled = enabled

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
        self._margin = 0
        self._width = window_width - 2*self._margin
        self._height = window_height - 2*self._margin
        glViewport(0, 0, window_width, window_height)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glOrtho(0.0, self.window_width, self.window_height, 0.0, -1.0, 1.0)
        glMatrixMode(GL_MODELVIEW)
        glTranslatef(self._margin, self._margin, 0)

        self._mode_specific_renderer = self._get_mode_specific_renderer()
        if not self._mode_disables_observations_rendering():
            self._observations_layer.draw()
        self._render_according_to_mode()
        if self._reduction is not None:
            self._render_reduction()

    def _get_mode_specific_renderer(self):
        toolbar = self._parent.parent().parent().parent()
        mode = toolbar.get_mode()
        if mode in self._mode_specific_renderers:
            return self._mode_specific_renderers[mode]

    def _mode_disables_observations_rendering(self):
        if self._mode_specific_renderer is not None:
            return not self._mode_specific_renderer.should_render_observations()

    def _render_according_to_mode(self):
        if self._mode_specific_renderer is not None:
            self._mode_specific_renderer.render()

    def _render_observations(self):
        glColor4f(0, 0, 0, .1)
        glLineWidth(1.0)
        for segment in self._segments:
            self.render_line_strip(segment)

    def render_line_strip(self, segment):
        glBegin(GL_LINE_STRIP)
        for vertex in segment:
            self.vertex(vertex)
        glEnd()

    def _render_reduction(self):
        glColor3f(0, 0, 0)
        glPointSize(5.0)
        glBegin(GL_POINTS)
        self.vertex(self._reduction)
        glEnd()

    def vertex(self, normalized_reduction):
        x, y = self._normalized_reduction_to_explored_range(normalized_reduction)
        glVertex2f(x*self._width, y*self._height)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self._enabled:
            self._dragging = True

    def mouseReleaseEvent(self, event):
        self._dragging = False

    def mouseMoveEvent(self, event):
        if self._dragging:
            x = event.x()
            y = event.y()
            self._reduction[0] = self._parent.exploration_value_to_normalized_reduction_value(
                self.dimensions[0], float(x - self._margin) / self._width)
            self._reduction[1] = self._parent.exploration_value_to_normalized_reduction_value(
                self.dimensions[1], float(y - self._margin) / self._height)
            self._parent.reduction_changed_interactively()
            
    def get_reduction(self):
        reduction = self._reduction_all_dimensions
        reduction[self.dimensions[0]] = self._reduction[0]
        reduction[self.dimensions[1]] = self._reduction[1]
        return reduction

    def _normalized_reduction_to_explored_range(self, normalized_reduction):
        return numpy.array([
                self._normalized_reduction_value_to_explored_range(n, normalized_reduction[n])
                for n in range(2)])

    def _normalized_reduction_value_to_explored_range(self, n, value):
        return self._parent.normalized_reduction_value_to_exploration_value(
            self.dimensions[n], value)

class MapViewRenderer:
    def __init__(self, map_view):
        self.map_view = map_view

    def should_render_observations(self):
        return True

    def updated_dimensions(self):
        pass

    def updated_normalized_observed_reductions(self):
        pass

class ImitateMapViewRenderer(MapViewRenderer):
    def __init__(self, *args, **kwargs):
        MapViewRenderer.__init__(self, *args, **kwargs)
        self._feature_match_result = None

    def get_event_handlers(self):
        return {Event.FEATURE_MATCH_RESULT: self._set_feature_match_result}

    def _set_feature_match_result(self, event):
        self._feature_match_result = event.content

    def render(self):
        if self._feature_match_result is not None:
            self._render_feature_matches()

    def _render_feature_matches(self):
        distances = [
            feature_match["distance"]
            for feature_match in
            self._feature_match_result]
        normalized_distances = self._normalize(distances)
        for feature_match, normalized_distance in zip(self._feature_match_result, normalized_distances):
            normalized_reduction = self.map_view.student.normalize_reduction(
                feature_match["reduction"])
            opacity = 1 - normalized_distance * 0.7
            if feature_match["is_target"]:
                glPointSize(11.0)
            else:
                glPointSize(8.0)
            glBegin(GL_POINTS)
            glColor4f(0, .6, 0, opacity)
            self.map_view.vertex(normalized_reduction[self.map_view.dimensions])
            glEnd()

    def _normalize(self, values):
        min_value = min(values)
        max_value = max(values)
        values_range = max_value - min_value
        if values_range == 0:
            return [.5] * len(values)
        else:
            return (values - min_value) / values_range

class ImproviseMapViewRenderer(MapViewRenderer):
    def __init__(self, *args, **kwargs):
        MapViewRenderer.__init__(self, *args, **kwargs)
        self._improvise_path = None

    def get_event_handlers(self):
        return {Event.IMPROVISE_PATH: self._set_improvise_path}

    def _set_improvise_path(self, event):
        self._improvise_path = numpy.array(event.content)

    def render(self):
        if self._improvise_path is not None:
            self._render_path(self._improvise_path)

    def _render_path(self, path):
        glPushAttrib(GL_ENABLE_BIT)
        glLineStipple(4, 0xAAAA)
        glEnable(GL_LINE_STIPPLE)
        glColor4f(0, 0, 0, .6)
        glLineWidth(2.0)
        self.map_view.render_line_strip(path[:,self.map_view.dimensions])
        glPopAttrib()

class FlaneurMapViewRenderer(MapViewRenderer):
    def __init__(self, *args, **kwargs):
        MapViewRenderer.__init__(self, *args, **kwargs)
        self._neighbors_center = None
        self._map_points_layer = Layer(self._render_map_points)

    def get_event_handlers(self):
        return {Event.NEIGHBORS_CENTER: self._set_neighbors_center}

    def _set_neighbors_center(self, event):
        self._neighbors_center = event.content

    def render(self):
        self._map_points_layer.draw()
        if self._neighbors_center is not None:
            self._render_neighbors_center()

    def _render_map_points(self):
        glColor3f(.5, .5, .5)
        glPointSize(1.0)
        glBegin(GL_POINTS)
        for map_point in self.map_view.normalized_observed_reductions:
            self.map_view.vertex(map_point[self.map_view.dimensions])
        glEnd()

    def _render_neighbors_center(self):
        glColor3f(.8, .2, .2)
        glPointSize(3.0)
        glBegin(GL_POINTS)
        self.map_view.vertex(self._neighbors_center[self.map_view.dimensions])
        glEnd()

    def should_render_observations(self):
        return False

    def updated_dimensions(self):
        self._map_points_layer.refresh()

    def updated_normalized_observed_reductions(self):
        self._map_points_layer.refresh()

class HybridMapViewRenderer(FlaneurMapViewRenderer, ImitateMapViewRenderer):
    def __init__(self, *args, **kwargs):
        FlaneurMapViewRenderer.__init__(self, *args, **kwargs)
        ImitateMapViewRenderer.__init__(self, *args, **kwargs)

    def get_event_handlers(self):
        return dict(
            list(FlaneurMapViewRenderer.get_event_handlers(self).items()) +
            list(ImitateMapViewRenderer.get_event_handlers(self).items()))

    def render(self):
        FlaneurMapViewRenderer.render(self)
        ImitateMapViewRenderer.render(self)

    def should_render_observations(self):
        return False
