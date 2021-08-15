from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from PyQt4 import QtCore, QtGui
import math
import collections
import numpy
from ui.scene import Scene
from ui.window import Window
from ui.floor_grid import FloorGrid
from feature_extraction import FeatureExtractor
from text_renderer import GlutTextRenderer

CAMERA_Y_SPEED = 1
CAMERA_KEY_SPEED = 40
CAMERA_DRAG_SPEED = .1
PROJECTION_NEAR = 0.1
PROJECTION_FAR = 20000.0
LOG_HEIGHT = 50
SKELETON_WIDTH_SELECTED = 2
SKELETON_WIDTH_UNSELECTED = 1
SKELETON_COLOR_SELECTED = (0, 0, 0)
SKELETON_COLOR_UNSELECTED = (.2, .2, .4)
SKELETON_COLOR_BELOW_FLOOR = (1, 0, 0)
CENTER_POSITION_SYMBOL_SIZE = 200
TRACKER_PITCH_SPEED = .1
TRACKER_Y_POSITION_SPEED = .5
ASSUMED_VIEW_DISTANCE = 5000
ORIENTATION_ARROW_LENGTH = 1000
ORIENTATION_ARROWHEAD_SIZE = 100

class TrackedUsersScene(Scene):
    def __init__(self, parent):
        Scene.__init__(self, parent, parent.args,
                       camera_y_speed=CAMERA_Y_SPEED,
                       camera_key_speed=CAMERA_KEY_SPEED,
                       camera_drag_speed=CAMERA_DRAG_SPEED)
        self._dragging_tracker_y_position = False
        self._dragging_tracker_pitch = False
        self.is_rendering = False
        self._floor = FloorGrid(
            num_cells=30,
            size=30000,
            y=self.parent().floor_y,
            floor_color=(0,0,0,0.2),
            background_color=(1,1,1,0))

    def initializeGL(self):
        glClearColor(1.0, 1.0, 1.0, 0.0)
        glClearAccum(0.0, 0.0, 0.0, 0.0)
        glClearDepth(1.0)
        glEnable(GL_POINT_SMOOTH)

        glShadeModel(GL_SMOOTH)
        glEnable(GL_LINE_SMOOTH)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glutInit(sys.argv)

    def paintGL(self):
        self.is_rendering = True

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        self.configure_3d_projection(pixdx=-100, pixdy=0, fovy=40.0,
                                     near=PROJECTION_NEAR, far=PROJECTION_FAR)
        self.render_3d_scene()

        self.configure_2d_projection(0.0, self.width, 0.0, self.height)
        self._render_frame_timestamp()
        self._render_system_state()
        if self.args.enable_features:
            self._render_features()

        if self.parent().show_positions_action.isChecked():
            self._print_positions()

        self.is_rendering = False

    def render_3d_scene(self):
        self._floor.render(
            center_x=0,
            center_z=0,
            camera_x=self._camera_position[0],
            camera_z=self._camera_position[2])

        if self.parent().show_field_of_view_action.isChecked():
            self._draw_field_of_view_boundary()
            self._draw_center_position()
            self._draw_active_area()

        self._selected_user = self.parent().interpreter.get_selected_user()

        for user in self.parent().interpreter.get_users():
            self._draw_user(user)

    def _draw_field_of_view_boundary(self):
        radius = ASSUMED_VIEW_DISTANCE
        center_x = 0
        center_z = 0

        glColor3f(0, 0.5, 0)
        self._draw_circle_on_floor(center_x, center_z, radius,
                                   from_angle=math.pi/4, angular_size=math.pi/2,
                                   as_segment=True)

    def _draw_circle_on_floor(self, center_x, center_z, radius,
                              from_angle=0, angular_size=math.pi*2,
                              as_segment=False,
                              resolution=50):
        y = self.parent().floor_y
        glBegin(GL_LINE_STRIP)

        if as_segment:
            glVertex3f(center_x, y, center_z)

        for i in range(resolution):
            angle = from_angle + angular_size * float(i) / (resolution-1)
            x = center_x + radius * math.cos(angle)
            z = center_z + radius * math.sin(angle)
            glVertex3f(x, y, z)

        if as_segment:
            glVertex3f(center_x, y, center_z)

        glEnd()

    def _draw_user(self, user):
        self._draw_label(user)
        self._draw_intensity(user)
        self._draw_skeleton(user)
        if self.parent().orientation_action.isChecked():
            self._draw_orientation(user)

    def _draw_skeleton(self, user):
        if self.args.joint_size > 0:
            self._draw_joints(user)
        self._draw_limbs(user)

    def _draw_joints(self, user):
        glPointSize(self.args.joint_size)
        glBegin(GL_POINTS)
        for joint_name in ["head",
                           "neck",
                           "torso",
                           "left_shoulder",
                           "left_elbow",
                           "left_hand",
                           "left_hip",
                           "left_knee",
                           "left_foot",
                           "right_shoulder",
                           "right_elbow",
                           "right_hand",
                           "right_hip",
                           "right_knee",
                           "right_foot",
                           ]:
            glVertex3f(*user.get_joint(joint_name).get_position())
        glEnd()

    def _draw_limbs(self, user):
        if user == self._selected_user:
            line_width = SKELETON_WIDTH_SELECTED
        else:
            line_width = SKELETON_WIDTH_UNSELECTED
        glLineWidth(line_width)
        self._draw_limb(user, "head", "neck")
        self._draw_limb(user, "left_shoulder", "neck")
        self._draw_limb(user, "right_shoulder", "neck")
        self._draw_limb(user, "left_shoulder", "left_elbow")
        self._draw_limb(user, "left_elbow", "left_hand")
        self._draw_limb(user, "right_shoulder", "right_elbow")
        self._draw_limb(user, "right_elbow", "right_hand")
        self._draw_limb(user, "left_shoulder", "right_shoulder")
        self._draw_limb(user, "neck", "torso")
        self._draw_limb(user, "left_hip", "torso")
        self._draw_limb(user, "right_hip", "torso")
        self._draw_limb(user, "left_hip", "left_knee")
        self._draw_limb(user, "left_knee", "left_foot")
        self._draw_limb(user, "right_hip", "right_knee")
        self._draw_limb(user, "right_knee", "right_foot")

    def _draw_label(self, user):
        head_position = user.get_joint("head").get_position()
        glColor3f(0, 0, 0)
        position = head_position + [0, 140, 0]
        self._draw_text(str(user.get_id()), size=100,
                        x=position[0], y=position[1], z=position[2],
                        h_align="center",
                        three_d=True)

    def _draw_intensity(self, user):
        head_position = user.get_joint("head").get_position()
        position = head_position + [150, 140, 0]
        intensity = user.get_intensity()

        glColor3f(.8, .8, 1)
        self._draw_solid_cube(*position, sx=70, sz=70, sy=self._intensity_as_height(
                self.parent().interpreter.intensity_ceiling))

        glColor3f(.5, .5, 1)
        self._draw_solid_cube(*position, sx=70, sz=70, sy=self._intensity_as_height(intensity))

        glColor3f(.5, .5, 1)
        self._draw_text("%.1f" % intensity, size=100,
                        x=position[0],
                        y=position[1] - 100,
                        z=position[2],
                        h_align="center",
                        three_d=True)

    def _intensity_as_height(self, intensity):
        return intensity * 3

    def _draw_solid_cube(self, x, y, z, sx, sy, sz, y_align_bottom=True):
        if y_align_bottom:
            y += sy/2
        glPushMatrix()
        glTranslatef(x, y, z)
        glScale(sx, sy, sz)
        glutSolidCube(1)
        glPopMatrix()

    def _draw_limb(self, user, name1, name2):
        vertices = self._split_vertices_at_floor(
            user.get_joint(name1).get_position(),
            user.get_joint(name2).get_position())

        confidence = min([user.get_joint(name1).get_position_confidence(),
                          user.get_joint(name2).get_position_confidence()])

        self._draw_solid_limb(user, confidence, vertices)
        self._draw_limb_shadow(user, confidence, vertices)

    def _draw_solid_limb(self, user, confidence, vertices):
        glBegin(GL_LINES)
        for n in range(len(vertices) - 1):
            vertex1 = vertices[n]
            vertex2 = vertices[n+1]
            self._set_color_by_joint(user, confidence, vertex1, vertex2)
            glVertex3f(*vertex1)
            glVertex3f(*vertex2)
        glEnd()

    def _draw_limb_shadow(self, user, confidence, vertices):
        glBegin(GL_LINES)
        for n in range(len(vertices) - 1):
            vertex1 = vertices[n]
            vertex2 = vertices[n+1]
            if vertex1[1] > self.parent().floor_y and vertex2[1] > self.parent().floor_y:
                self._set_shadow_color_by_joint(user, confidence)
                glVertex3f(vertex1[0], self.parent().floor_y, vertex1[2])
                glVertex3f(vertex2[0], self.parent().floor_y, vertex2[2])
        glEnd()

    def _split_vertices_at_floor(self, vertex1, vertex2):
        floor_y = self.parent().floor_y
        if (vertex1[1] < floor_y < vertex2[1] or
            vertex1[1] > floor_y > vertex2[1]):
            floor_x = vertex1[0] + (vertex2[0] - vertex1[0]) / (vertex2[1] - vertex1[1]) * (floor_y - vertex1[1])
            floor_z = vertex1[2] + (vertex2[2] - vertex1[2]) / (vertex2[1] - vertex1[1]) * (floor_y - vertex1[1])
            return [vertex1,
                    numpy.array([floor_x, floor_y, floor_z]),
                    vertex2]
        else:
            return [vertex1, vertex2]

    def _set_color_by_joint(self, user, confidence, vertex1, vertex2):
        a = 1 - (.8 - confidence * .8)
        if vertex1[1] <= self.parent().floor_y and vertex2[1] <= self.parent().floor_y:
            r, g, b = SKELETON_COLOR_BELOW_FLOOR
        else:
            if user == self._selected_user:
                r, g, b = SKELETON_COLOR_SELECTED
            else:
                r, g, b = SKELETON_COLOR_UNSELECTED
        glColor4f(r, g, b, a)

    def _set_shadow_color_by_joint(self, user, confidence):
        a = (1 - (.8 - confidence * .8)) * .3
        if user == self._selected_user:
            r, g, b = SKELETON_COLOR_SELECTED
        else:
            r, g, b = SKELETON_COLOR_UNSELECTED
        glColor4f(r, g, b, a)

    def _draw_text(self, text, size, x, y, z, font=GLUT_STROKE_ROMAN, spacing=None,
                  v_align="left", h_align="top", three_d=False):
        self._text_renderer(text, size, font).render(x, y, z, v_align, h_align, three_d)

    def _text_renderer(self, text, size, font):
        return GlutTextRenderer(self, text, size, font)

    def _draw_center_position(self):
        glLineWidth(1)
        glColor3f(0, 0.5, 0)
        x = self.parent().interpreter.active_area_center_x
        z = self.parent().interpreter.active_area_center_z
        y = self.parent().floor_y
        x1 = x - CENTER_POSITION_SYMBOL_SIZE/2
        x2 = x + CENTER_POSITION_SYMBOL_SIZE/2
        z1 = z - CENTER_POSITION_SYMBOL_SIZE/2
        z2 = z + CENTER_POSITION_SYMBOL_SIZE/2
        glBegin(GL_LINES)
        glVertex3f(x1, y, z1)
        glVertex3f(x2, y, z2)
        glVertex3f(x2, y, z1)
        glVertex3f(x1, y, z2)
        glEnd()

    def _draw_active_area(self):
        self._draw_circle_on_floor(
            center_x=self.parent().interpreter.active_area_center_x,
            center_z=self.parent().interpreter.active_area_center_z,
            radius=self.parent().interpreter.active_area_radius)

    def _draw_orientation(self, user):
        torso = user.get_joint("torso")
        y = self.parent().floor_y
        x, _, z = torso.get_position()
        a = 1 - (.8 - torso.get_orientation_confidence() * .8)        
        glColor4f(0, 1, 0, a)
        glPushMatrix()
        glTranslatef(x, y, z)
        glRotatef(math.degrees(user.get_root_vertical_orientation() + math.pi/2), 0, 1, 0)
        glBegin(GL_LINES)
        glVertex3f(0, 0, 0)
        glVertex3f(ORIENTATION_ARROW_LENGTH, 0, 0)
        glVertex3f(ORIENTATION_ARROW_LENGTH, 0, 0)
        glVertex3f(ORIENTATION_ARROW_LENGTH-ORIENTATION_ARROWHEAD_SIZE, 0, -ORIENTATION_ARROWHEAD_SIZE)
        glVertex3f(ORIENTATION_ARROW_LENGTH, 0, 0)
        glVertex3f(ORIENTATION_ARROW_LENGTH-ORIENTATION_ARROWHEAD_SIZE, 0, +ORIENTATION_ARROWHEAD_SIZE)
        glEnd()
        glPopMatrix()

    def _print_positions(self):
        for user in self.parent().interpreter.get_users():
            torso_x, _, torso_z = user.get_joint("torso").get_position()
            bottom_y = min([user.get_joint("left_foot").get_position()[1],
                            user.get_joint("right_foot").get_position()[1]])
            print("[%s] torso: %.1f,%.1f  bottom_y: %.1f" % (user.get_id(), torso_x, torso_z, bottom_y))

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and \
            QtGui.QApplication.instance().keyboardModifiers() == QtCore.Qt.ControlModifier:
            self._dragging_tracker_pitch = True
        elif event.button() == QtCore.Qt.RightButton and \
            QtGui.QApplication.instance().keyboardModifiers() == QtCore.Qt.ControlModifier:
            self._dragging_tracker_y_position = True
        else:
            Scene.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        x = event.x()
        y = event.y()
        if self._dragging_tracker_pitch:
            self.parent().interpreter.set_tracker_pitch(
                self.parent().interpreter.get_tracker_pitch() +
                TRACKER_PITCH_SPEED * (y - self._drag_y_previous))
            self._drag_y_previous = y
            self.updateGL()
        elif self._dragging_tracker_y_position:
            self.parent().interpreter.tracker_y_position += TRACKER_Y_POSITION_SPEED * (
                y - self._drag_y_previous)
            self._drag_y_previous = y
            self.updateGL()
        else:
            Scene.mouseMoveEvent(self, event)
            if self._dragging_orientation or self._dragging_y_position:
                self.updateGL()

    def mouseReleaseEvent(self, event):
        self._dragging_tracker_pitch = False
        self._dragging_tracker_y_position = False
        Scene.mouseReleaseEvent(self, event)

    def print_tracker_settings(self):
        print("%.3f,%.3f" % (
            self.parent().interpreter.tracker_y_position,
            self.parent().interpreter.get_tracker_pitch()))

    def _render_frame_timestamp(self):
        if self.parent().frame:
            glColor4f(0, 0, 0, .5)
            self._draw_text(
                "%.1f" % (self.parent().frame["timestamp"] / 1000),
                size=10, x=5, y=5, z=0)

    def _render_system_state(self):
        if self.parent().frame:
            glColor4f(0, .5, 0, .5)
            self._draw_text(
                self.parent().interpreter.get_system_state(),
                size=14, x=5, y=20, z=0)

    def _render_features(self):
        if self.parent().frame and self.parent().frame["selected_user"] is not None:
            glColor4f(.5, 0, 0, .5)
            i = 0
            for name, value in zip(FeatureExtractor.FEATURES, self.parent().frame["features"]):
                y =  5 + i * 14
                self._draw_text(
                    name,
                    size=12, x=400, y=y, z=0)
                self._draw_text(
                    "%.2f" % value,
                    size=12, x=500, y=y, z=0)
                i += 1

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

class TrackedUsersViewer(Window):
    def __init__(self, interpreter, args, enable_log_replay=False, scene_class=TrackedUsersScene):
        Window.__init__(self, args)
        self.args = args
        self._enable_log_replay = enable_log_replay
        self.interpreter = interpreter
        self.frame = None
        self.floor_y = args.floor_y
        self._layout = QtGui.QVBoxLayout()
        self._layout.setSpacing(0)
        self._layout.setMargin(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)

        self._scene = scene_class(self)
        size_policy = QtGui.QSizePolicy(
            QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        size_policy.setVerticalStretch(2)
        size_policy.setHorizontalStretch(2)
        self._scene.setSizePolicy(size_policy)

        self._layout.addWidget(self._scene)
        self._log_widget = LogWidget(self)
        self._layout.addWidget(self._log_widget)
        self._create_menu()

        if self.args.fullscreen:
            self.give_keyboard_focus_to_fullscreen_window()
            self._fullscreen_action.toggle()

    @staticmethod
    def add_parser_arguments(parser):
        Window.add_parser_arguments(parser)
        parser.add_argument("--camera", help="posX,posY,posZ,orientY,orientX",
                            default="59.964,-1578.000,2562.016,-188.500,16.000")
        parser.add_argument("--floor-y", type=float, default=0)
        parser.add_argument("--joint-size", type=float)
        parser.add_argument("--show-orientation", action="store_true")

    def _create_menu(self):
        self._menu_bar = QtGui.QMenuBar()
        self._layout.setMenuBar(self._menu_bar)
        self._create_main_menu()
        self._create_view_menu()
        if self._enable_log_replay:
            self._create_replay_menu()

    def _create_main_menu(self):
        self._main_menu = self._menu_bar.addMenu("Main")
        self._add_show_camera_settings_action()
        self._add_show_tracker_settings_action()
        self._add_show_positions_action()

    def _add_show_camera_settings_action(self):
        action = QtGui.QAction('Show camera settings', self)
        action.triggered.connect(self._scene.print_camera_settings)
        self._main_menu.addAction(action)

    def _add_show_tracker_settings_action(self):
        action = QtGui.QAction('Show tracker settings', self)
        action.triggered.connect(self._scene.print_tracker_settings)
        self._main_menu.addAction(action)

    def _add_show_positions_action(self):
        self.show_positions_action = QtGui.QAction('Show positions', self)
        self.show_positions_action.setCheckable(True)
        self.show_positions_action.setShortcut("Ctrl+Shift+p")
        self._main_menu.addAction(self.show_positions_action)

    def _create_view_menu(self):
        self._view_menu = self._menu_bar.addMenu("View")
        self._add_show_field_of_view_action()
        self._add_fullscreen_action()
        self._add_auto_refresh_action()
        self._add_orientation_action()

    def _add_show_field_of_view_action(self):
        self.show_field_of_view_action = QtGui.QAction('Show field of view', self)
        self.show_field_of_view_action.setCheckable(True)
        self.show_field_of_view_action.setShortcut("Ctrl+p")
        self.show_field_of_view_action.triggered.connect(self._scene.updateGL)
        self._view_menu.addAction(self.show_field_of_view_action)
        self.show_field_of_view_action.toggle()

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

    def _add_auto_refresh_action(self):
        self.auto_refresh_action = QtGui.QAction('Auto refresh', self)
        self.auto_refresh_action.setCheckable(True)
        self.auto_refresh_action.setShortcut('r')
        self._view_menu.addAction(self.auto_refresh_action)
        self.auto_refresh_action.toggle()

    def _add_orientation_action(self):
        self.orientation_action = QtGui.QAction('Orientation', self)
        self.orientation_action.setCheckable(True)
        self.orientation_action.setShortcut('o')
        self.orientation_action.setChecked(self.args.show_orientation)
        self._view_menu.addAction(self.orientation_action)

    def _create_replay_menu(self):
        self._replay_menu = self._menu_bar.addMenu("Replay")
        self._add_replay_slower_action()
        self._add_replay_faster_action()
        self._add_reset_replay_speed_action()

    def _add_replay_slower_action(self):
        action = QtGui.QAction("Replay slower", self)
        action.setShortcut("-")
        action.triggered.connect(lambda: self._change_replay_speed(-1))
        self._replay_menu.addAction(action)

    def _add_replay_faster_action(self):
        action = QtGui.QAction("Replay faster", self)
        action.setShortcut("+")
        action.triggered.connect(lambda: self._change_replay_speed(+1))
        self._replay_menu.addAction(action)

    def _add_reset_replay_speed_action(self):
        action = QtGui.QAction("Reset replay speed", self)
        action.setShortcut("0")
        action.triggered.connect(lambda: self._set_replay_speed(1))
        self._replay_menu.addAction(action)

    def _change_replay_speed(self, factor):
        current_speed = self.interpreter.log_replay_speed
        new_speed = max(current_speed + factor * 0.2, 0.1)
        self._set_replay_speed(new_speed)

    def _set_replay_speed(self, speed):
        self.interpreter.log_replay_speed = speed
        print("replay speed: %.1f" % speed)

    def keyPressEvent(self, event):
        key = event.key()
        if key == QtCore.Qt.Key_Escape:
            if self._fullscreen_action.isChecked():
                self._fullscreen_action.toggle()
        else:
            if self._scene.keyPressEvent(event):
                self._scene.updateGL()
            QtGui.QWidget.keyPressEvent(self, event)

    def sizeHint(self):
        return QtCore.QSize(640, 480)

    def process_frame(self, frame):
        self.frame = frame
        self._update_log_widget()
        if self.auto_refresh_action.isChecked() and not self._scene.is_rendering:
            QtGui.QApplication.postEvent(self, CustomQtEvent(self._scene.updateGL))
            
    def _update_log_widget(self):
        for user_id, state in self.frame["user_states"]:
            self.log(self.frame["timestamp"], "%s %s" % (state, user_id))

    def log(self, timestamp_ms, message):
        QtGui.QApplication.postEvent(self, CustomQtEvent(lambda: self._log(
            timestamp_ms, message)))

    def _log(self, timestamp_ms, message):
        self._log_widget.append("%.1f %s\n" % (timestamp_ms / 1000, message))

    def customEvent(self, custom_qt_event):
        custom_qt_event.callback()

class CustomQtEvent(QtCore.QEvent):
    EVENT_TYPE = QtCore.QEvent.Type(QtCore.QEvent.registerEventType())

    def __init__(self, callback):
        QtCore.QEvent.__init__(self, CustomQtEvent.EVENT_TYPE)
        self.callback = callback
