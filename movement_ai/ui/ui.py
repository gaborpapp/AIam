from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from PyQt4 import QtCore, QtGui, QtOpenGL
import math
import numpy
from parameters import *
from event import Event
from event_listener import EventListener
from parameters_form import ParametersForm
from color_schemes import *
from exporter import Exporter
from scene import Scene
from window import Window
from floor_grid import FloorGrid
from floor_spots import FloorSpots
from floor_checkerboard import FloorCheckerboard
from text_renderer import GlutTextRenderer
from control_layout import ControlLayout
import shutil

TOOLBAR_HEIGHT = 350
SLIDER_PRECISION = 1000
FOCUS_RADIUS = .75
VIDEO_EXPORT_PATH = "rendered_video"
CAMERA_Y_SPEED = .01
CAMERA_KEY_SPEED = .1
CAMERA_DRAG_SPEED = .1
FRAME_RATE = 30.0
ORIGIN_SIZE = 1

FLOOR_RENDERERS = {
    "grid": (FloorGrid, {"num_cells": 30, "size": 100}),
    "spots": (FloorSpots, {}),
    "checkerboard": (FloorCheckerboard, {
            "num_cells": 26, "size": 26,
            "board_color1": (.2, .2, .2, 1),
            "board_color2": (.3, .3, .3, 1)}),
    }

class BvhScene(Scene):
    @staticmethod
    def add_parser_arguments(parser):
        pass

    def __init__(self, parent, bvh_reader, args):
        self._parent = parent
        self.bvh_reader = bvh_reader
        if args.floor and args.floor_renderer:
            self.view_floor = True
        else:
            self.view_floor = False
        self.view_input = True
        self.view_frame_count = False
        self.view_origin = False
        self._focus = None
        self.processed_input = None
        self.processed_output = None
        self.processed_io_blend = None
        Scene.__init__(self, parent, args,
                       camera_y_speed=CAMERA_Y_SPEED,
                       camera_key_speed=CAMERA_KEY_SPEED,
                       camera_drag_speed=CAMERA_DRAG_SPEED)
        self.frame_count = None
        if args.image:
            self._image = QtGui.QImage(args.image)
        self._exporting_video = False
        if self.view_floor:
            self._floor = None
            self._floor_renderer_class, self._floor_renderer_args = \
                FLOOR_RENDERERS[args.floor_renderer]
        if args.fixed_size:
            self.setFixedSize(args.preferred_width, args.preferred_height)

        if args.z_up:
            self.bvh_coordinate_left = 0
            self.bvh_coordinate_up = 2
            self.bvh_coordinate_far = 1
        else:
            self.bvh_coordinate_left = 0
            self.bvh_coordinate_up = 1
            self.bvh_coordinate_far = 2

    def _set_focus(self):
        self._focus = self.get_root_vertex(self.processed_output)

    def _output_outside_focus(self):
        if self._focus is not None:
            distance = numpy.linalg.norm(
                self.get_root_vertex(self.processed_output) - self._focus)
            return distance > FOCUS_RADIUS

    def received_output(self, processed_output):
        self.processed_output = processed_output
        if self._focus is None:
            self._set_focus()
        if self.following_output() and self._output_outside_focus():
            self.centralize_output(processed_output)
            self._set_focus()

    def received_io_blend(self, processed_io_blend):
        self.processed_io_blend = processed_io_blend
        
    def render(self):
        if self.args.image:
            self._render_image()
        self.configure_3d_projection()
        if self.view_floor:
            self._draw_floor()
        if self.view_origin:
            self._draw_origin()
        if self._parent.focus_action.isChecked():
            self._draw_focus()
        self._update_camera_translation()
        self.render_io()
        if hasattr(self._parent, "orientation_action") and self._parent.orientation_action.isChecked():
            root_vertical_orientation = self._parent.get_root_vertical_orientation()
            if root_vertical_orientation is not None:
                self.render_root_vertical_orientation(root_vertical_orientation)
        if self._exporting_video:
            self._exporter.export_frame()
            self._parent.send_event(Event(Event.PROCEED_TO_NEXT_FRAME))

        if self.view_frame_count and self.frame_count is not None:
            self.configure_2d_projection(0.0, self.width, 0.0, self.height)
            glColor3f(*self._parent.color_scheme["input"])
            self._draw_text(
                "%d" % self.frame_count,
                size=14, x=5, y=20, z=0)

    def _draw_text(self, text, size, x, y, z, font=GLUT_STROKE_ROMAN, spacing=None,
                  v_align="left", h_align="top", three_d=False):
        self._text_renderer(text, size, font).render(x, y, z, v_align, h_align, three_d)

    def _text_renderer(self, text, size, font):
        return GlutTextRenderer(self, text, size, font)

    def render_io(self):
        if self.view_input:
            self._draw_io(self.processed_input, self.draw_input, self.args.input_y_offset)

        if self._parent.split_output_and_io_blend:
            self._draw_io(self.processed_output, self.draw_output, self.args.output_y_offset)
            self._draw_io(self.processed_io_blend, self.draw_io_blend, self.args.output_y_offset)
        else:
            if self.processed_io_blend is None:
                self._draw_io(self.processed_output, self.draw_output, self.args.output_y_offset)
            else:
                self._draw_io(self.processed_io_blend, self.draw_output, self.args.output_y_offset)

    def _draw_floor(self):
        if self.processed_output is not None:
            center_x, center_z = self.get_root_vertex(self.processed_output)
            camera_translation = self.camera_translation()
            camera_x = self._camera_position[0] + camera_translation[0]
            camera_z = self._camera_position[2] + camera_translation[1]

            if self._floor is None:
                self._floor = self._create_floor_renderer()
            self._floor.render(
                center_x,
                center_z,
                camera_x,
                camera_z)

    def _draw_origin(self):
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
        
    def _create_floor_renderer(self):
        kwargs = self._floor_renderer_args
        kwargs["floor_color"] = self._parent.color_scheme["floor"]
        kwargs["background_color"] = self._parent.color_scheme["background"]
        return self._floor_renderer_class(**kwargs)

    def _render_image(self):
        self.configure_2d_projection(0.0, self.width, self.height, 0.0)
        glColor4f(1, 1, 1, 1)
        glEnable(GL_TEXTURE_2D)
        glPushMatrix()
        glTranslatef(
            self.width - self._image.width() * self.args.image_scale - self.args.image_margin,
            self.args.image_margin,
            0)
        glScalef(self.args.image_scale, self.args.image_scale, 1)
        self.drawTexture(QtCore.QPointF(0, 0), self._image_texture)
        glPopMatrix()
        glDisable(GL_TEXTURE_2D)

    def configure_3d_projection(self):
        Scene.configure_3d_projection(self, -100, 0)

    def _draw_io(self, value, rendering_method, y_offset, **kwargs):
        glPushMatrix()
        glTranslatef(0, y_offset, 0)
        if self.args.unit_cube:
            self._draw_unit_cube()
        if value is not None:
            rendering_method(value, **kwargs)
        glPopMatrix()

    def initializeGL(self):
        glClearAccum(0.0, 0.0, 0.0, 0.0)
        glClearDepth(1.0)
        glShadeModel(GL_SMOOTH)
        glEnable(GL_LINE_SMOOTH)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glutInit(sys.argv)
        if self.args.image:
            self._image_texture = self.bindTexture(self._image)

    def paintGL(self):
        glClearColor(*self._parent.color_scheme["background"])
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(self.margin, self.margin, 0)
        self.render()

    def _draw_unit_cube(self):
        glLineWidth(1.0)
        glColor4f(*self._parent.color_scheme["unit_cube"])
        glutWireCube(2.0)

    def _draw_focus(self):
        glLineWidth(1.0)
        glColor4f(*self._parent.color_scheme["focus"])
        self.draw_circle_on_floor(self._focus[0], self._focus[1], FOCUS_RADIUS)

    def following_output(self):
        return self._parent.following_output()

    def start_export_video(self):
        if os.path.exists(VIDEO_EXPORT_PATH):
            shutil.rmtree(VIDEO_EXPORT_PATH)
        os.mkdir(VIDEO_EXPORT_PATH)
        self._exporter = Exporter(VIDEO_EXPORT_PATH, 0, 0, self.width, self.height)
        self._exporting_video = True
        print "exporting video to %s" % VIDEO_EXPORT_PATH
        self._parent.send_event(Event(Event.STOP))
        self._parent.send_event(Event(Event.PROCEED_TO_NEXT_FRAME))

    def stop_export_video(self):
        self._exporting_video = False
        print "stopped exporting video"

    def bvh_vertex(self, v):
        glVertex3f(
            v[self.bvh_coordinate_left],
            v[self.bvh_coordinate_up],
            v[self.bvh_coordinate_far])

    def get_root_vertical_orientation(self):
        pass

class ExperimentToolbar(QtGui.QWidget):
    def __init__(self, parent, args):
        self.args = args
        QtOpenGL.QGLWidget.__init__(self, parent)

    def refresh(self):
        pass

    def add_parameter_fields(self, parameters, parent):
        return ParametersForm(parameters, parent)

    def get_event_handlers(self):
        return {}

    def add_input_tab_widget(self, parent):
        if self.args.enable_follow or self.args.receive_from_pn:
            input_tab_widget = QtGui.QTabWidget()
            input_tab = QtGui.QWidget()
            layout = QtGui.QVBoxLayout()
            layout.setSpacing(0)
            layout.setMargin(0)
            input_tab.setLayout(layout)

            class InputParameters(Parameters):
                def __init__(self):
                    Parameters.__init__(self)
                    self.add_parameter("delay", type=float, default=0,
                                       choices=ParameterFloatRange(0., 5.))

            input_params = InputParameters()
            input_params.add_listener(self._send_changed_input_param)
            input_params_form = self.add_parameter_fields(input_params, layout)
            
            layout.addStretch(1)
            input_tab_widget.addTab(input_tab, "Input")
            parent.addWidget(input_tab_widget)

    def _send_changed_input_param(self, parameter):
        if parameter.name == "delay":
            self.parent().client.send_event(Event(Event.SET_INPUT_DELAY, parameter.value()))
        
    def add_entity_tab_widget(self, parent):
        if self.args.entity == "hierarchical":
            entity_tab_widget = QtGui.QTabWidget()
            entity_tab = QtGui.QWidget()
            layout = QtGui.QVBoxLayout()
            entity_tab.setLayout(layout)
            control_layout = ControlLayout()
            self._add_hierarchical_parameters(control_layout)
            layout.addLayout(control_layout.layout)
            layout.addStretch(1)
            entity_tab_widget.addTab(entity_tab, "Entity")
            parent.addWidget(entity_tab_widget)

    def _add_hierarchical_parameters(self, control_layout):
        control_layout.add_label("Friction")
        self.enable_friction_checkbox = self._create_enable_friction_checkbox()
        control_layout.add_control_widget(self.enable_friction_checkbox)

        if self.args.enable_io_blending:
            control_layout.add_label("Max angular step")
            self._max_angular_step_slider = self._create_max_angular_step_slider()
            control_layout.add_control_widget(self._max_angular_step_slider)

    def _create_enable_friction_checkbox(self):
        checkbox = QtGui.QCheckBox()
        checkbox.setEnabled(not self.args.enable_io_blending)
        checkbox.setChecked(self.args.friction)
        checkbox.stateChanged.connect(self._enable_friction_checkbox_changed)
        return checkbox

    def _enable_friction_checkbox_changed(self, event):
        self.parent().send_event(Event(Event.SET_FRICTION,
                                       self.enable_friction_checkbox.isChecked()))
        
    def _create_max_angular_step_slider(self):
        slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, SLIDER_PRECISION)
        slider.setSingleStep(1)
        slider.setValue(self.args.max_angular_step * SLIDER_PRECISION)
        slider.valueChanged.connect(lambda value: self._on_changed_max_angular_step_slider())
        return slider

    def _on_changed_max_angular_step_slider(self):
        max_angular_step = float(self._max_angular_step_slider.value()) / SLIDER_PRECISION
        self.parent().send_event(Event(Event.SET_MAX_ANGULAR_STEP, max_angular_step))

    def add_learning_tab_widget(self, parent):
        if self.parent().student.supports_incremental_learning():
            learning_tab_widget = QtGui.QTabWidget()
            learning_tab = QtGui.QWidget()
            layout = QtGui.QVBoxLayout()
            layout.setSpacing(0)
            layout.setMargin(0)
            learning_tab.setLayout(layout)

            default_learning_rate = self.args.learning_rate
            default_min_loss = self.args.target_training_loss
            
            class LearningParameters(Parameters):
                def __init__(self):
                    Parameters.__init__(self)
                    self.add_parameter("rate", type=float, default=default_learning_rate,
                                       choices=ParameterFloatRange(0., 1.))
                    self.add_parameter("add_noise", type=float, default=0,
                                       choices=ParameterFloatRange(0., 1.))
                    self.add_parameter("min_loss", type=float, default=default_min_loss,
                                       choices=ParameterFloatRange(0., 1.))

            learning_params = LearningParameters()
            learning_params.add_listener(self._send_changed_learning_param)
            learning_params_form = self.add_parameter_fields(learning_params, layout)

            loss_layout = QtGui.QHBoxLayout()
            loss_label = QtGui.QLabel("Loss")
            self.training_loss_value = QtGui.QLabel("")
            loss_layout.addWidget(loss_label)
            loss_layout.addWidget(self.training_loss_value)
            layout.addLayout(loss_layout)
            
            layout.addStretch(1)
            learning_tab_widget.addTab(learning_tab, "Learning")
            parent.addWidget(learning_tab_widget)

    def _send_changed_learning_param(self, parameter):
        if parameter.name == "rate":
            self.parent().client.send_event(Event(Event.SET_LEARNING_RATE, parameter.value()))
        elif parameter.name == "add_noise":
            self.parent().client.send_event(Event(Event.SET_MODEL_NOISE_TO_ADD, parameter.value()))
        elif parameter.name == "min_loss":
            self.parent().client.send_event(Event(Event.SET_MIN_TRAINING_LOSS, parameter.value()))

class MainWindow(Window, EventListener):
    @staticmethod
    def add_parser_arguments(parser):
        Window.add_parser_arguments(parser)
        parser.add_argument("--width", dest="preferred_width", type=int, default=1440)
        parser.add_argument("--height", dest="preferred_height", type=int, default=900)
        parser.add_argument("--fixed-size", action="store_true")
        parser.add_argument("--maximized", action="store_true")
        parser.add_argument("--camera", help="posX,posY,posZ,orientY,orientX",
                            default="-3.767,-1.400,-3.485,-55.500,18.500")
        parser.add_argument("--no-toolbar", action="store_true")
        parser.add_argument("--color-scheme", default="white")
        parser.add_argument("--image")
        parser.add_argument("--image-scale", type=float, default=1)
        parser.add_argument("--image-margin", type=int, default=0)
        parser.add_argument("--ui-event-log-target")
        parser.add_argument("--ui-event-log-source")
        parser.add_argument("--floor-renderer",
                            choices=FLOOR_RENDERERS.keys())

    def __init__(self, client, entity, student, bvh_reader, scene_widget_class, toolbar_class, args,
                 event_handlers={}):
        Window.__init__(self, args)
        self.client = client
        self.entity = entity
        self.student = student
        self.args = args

        self.split_output_and_io_blend = False
        self.toolbar = toolbar_class(self, args)
        event_handlers.update({
            Event.INPUT: self._handle_input,
            Event.OUTPUT: self._handle_output,
            Event.IO_BLEND: self._handle_io_blend,
            Event.FRAME_COUNT: self._handle_frame_count,
            Event.SET_FRICTION: self._update_enable_friction,
        })
        event_handlers.update(self.toolbar.get_event_handlers())
        EventListener.__init__(self, handlers=event_handlers)

        self.outer_vertical_layout = QtGui.QVBoxLayout()
        self.outer_vertical_layout.setSpacing(0)
        self.outer_vertical_layout.setMargin(0)
        self.outer_vertical_layout.setContentsMargins(0, 0, 0, 0)

        inner_vertical_layout = QtGui.QVBoxLayout()

        size_policy = QtGui.QSizePolicy(
            QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        size_policy.setVerticalStretch(2)
        size_policy.setHorizontalStretch(2)

        self._scene = scene_widget_class(self, bvh_reader, args)
        self._scene.setSizePolicy(size_policy)
        self._create_menu()
        inner_vertical_layout.addWidget(self._scene)

        if self.args.no_toolbar:
            self._hide_toolbar()
        else:
            self._show_toolbar()
        inner_vertical_layout.addWidget(self.toolbar)

        inner_vertical_layout.setAlignment(self.toolbar, QtCore.Qt.AlignTop)
        self.outer_vertical_layout.addLayout(inner_vertical_layout)
        self.setLayout(self.outer_vertical_layout)

        self._set_color_scheme(self.args.color_scheme)
        self.time_increment = 1.0 / FRAME_RATE

        self._update_timer = QtCore.QTimer(self)
        self._update_timer.setInterval(1000. / FRAME_RATE)
        QtCore.QObject.connect(self._update_timer, QtCore.SIGNAL('timeout()'), self.update_qgl_widgets)
        self._update_timer.start()

        if args.fixed_size:
            self.setFixedSize(self.args.preferred_width, self.args.preferred_height)
        if args.maximized:
            self.showMaximized()
        if self.args.fullscreen:
            self.give_keyboard_focus_to_fullscreen_window()
            self._fullscreen_action.toggle()

    def update_qgl_widgets(self):
        self._scene.updateGL()

    def start(self):
        if self.client:
            self.client.set_event_listener(self)

        if self.args.ui_event_log_target:
            self.set_event_log_target(self.args.ui_event_log_target)
        if self.args.ui_event_log_source:
            self.set_event_log_source(self.args.ui_event_log_source)
            self.process_event_log_in_new_thread()

    def received_event(self, event):
        callback = lambda: self.handle_event(event)
        QtGui.QApplication.postEvent(self, CustomQtEvent(callback))

    def sizeHint(self):
        return QtCore.QSize(self.args.preferred_width, self.args.preferred_height)

    def _create_menu(self):
        self._menu_bar = QtGui.QMenuBar()
        self.outer_vertical_layout.setMenuBar(self._menu_bar)
        self._create_main_menu()
        self._create_view_menu()
        self._create_color_scheme_menu()

    def _create_main_menu(self):
        self._main_menu = self._menu_bar.addMenu("&Main")
        self._add_toggleable_action(
            "Start", self._start,
            "Stop", self._stop,
            True, " ")
        self._add_next_frame_action()
        self._add_save_student_action()
        self._add_load_student_action()
        self._add_toggleable_action(
            '&Export BVH', lambda: self.send_event(Event(Event.START_EXPORT_BVH)),
            '&Stop export BVH', lambda: self.send_event(Event(Event.STOP_EXPORT_BVH)),
            False, 'Ctrl+E')
        self._add_toggleable_action(
            '&Export video', self._scene.start_export_video,
            '&Stop export video', self._scene.stop_export_video,
            False, 'F9')
        self._add_show_camera_settings_action()
        self._add_quit_action()

    def _start(self):
        self.send_event(Event(Event.START))

    def _stop(self):
        self.send_event(Event(Event.STOP))

    def _add_toggleable_action(self,
                               enable_title, enable_handler,
                               disable_title, disable_handler,
                               default, shortcut):
        enable_action = QtGui.QAction(enable_title, self)
        enable_action.setShortcut(shortcut)
        enable_action.triggered.connect(lambda: self._enable(enable_handler, enable_action, disable_action))
        enable_action.setEnabled(not default)
        self._main_menu.addAction(enable_action)

        disable_action = QtGui.QAction(disable_title, self)
        disable_action.setShortcut(shortcut)
        disable_action.triggered.connect(lambda: self._disable(disable_handler, enable_action, disable_action))
        disable_action.setEnabled(default)
        self._main_menu.addAction(disable_action)

    def _enable(self, handler, enable_action, disable_action):
        enable_action.setEnabled(False)
        disable_action.setEnabled(True)
        handler()

    def _disable(self, handler, enable_action, disable_action):
        disable_action.setEnabled(False)
        enable_action.setEnabled(True)
        handler()

    def _add_next_frame_action(self):
        action = QtGui.QAction("Next frame", self)
        action.setShortcut("n")
        action.triggered.connect(self._proceed_to_next_frame)
        self._main_menu.addAction(action)

    def _proceed_to_next_frame(self):
        self.send_event(Event(Event.PROCEED_TO_NEXT_FRAME))
        
    def _add_show_camera_settings_action(self):
        action = QtGui.QAction('Show camera settings', self)
        action.triggered.connect(self._scene.print_camera_settings)
        self._main_menu.addAction(action)
        
    def _add_quit_action(self):
        action = QtGui.QAction("&Quit", self)
        action.triggered.connect(QtGui.QApplication.exit)
        self._main_menu.addAction(action)

    def _add_save_student_action(self):
        action = QtGui.QAction("Save model...", self)
        action.setShortcut('Ctrl+S')
        action.triggered.connect(self._save_student)
        self._main_menu.addAction(action)

    def _save_student(self):
        filename = QtGui.QFileDialog.getSaveFileName(self, "Save model", filter="Model (*.model)")
        self.send_event(Event(Event.SAVE_STUDENT, str(filename)))

    def _add_load_student_action(self):
        action = QtGui.QAction("Load model...", self)
        action.setShortcut('Ctrl+O')
        action.triggered.connect(self._load_student)
        self._main_menu.addAction(action)

    def _load_student(self):
        filename = QtGui.QFileDialog.getOpenFileName(self, "Load model", filter="Model (*.model)")
        self.send_event(Event(Event.LOAD_STUDENT, str(filename)))

    def _create_view_menu(self):
        self._view_menu = self._menu_bar.addMenu("View")
        self._add_toolbar_action()
        self._add_origin_action()
        self._add_fullscreen_action()
        self._add_follow_output_action()
        self._add_assumed_focus_action()
        self._add_floor_action()
        self._add_input_action()
        self._add_frame_count_action()
        if self.args.entity == "hierarchical":
            self._add_orientation_action()

    def _add_toolbar_action(self):
        self._toolbar_action = QtGui.QAction('Toolbar', self)
        self._toolbar_action.setCheckable(True)
        self._toolbar_action.setChecked(not self.args.no_toolbar)
        self._toolbar_action.setShortcut('Ctrl+T')
        self._toolbar_action.toggled.connect(self._toggled_toolbar)
        self._view_menu.addAction(self._toolbar_action)

    def _toggled_toolbar(self):
        if self._toolbar_action.isChecked():
            self._show_toolbar()
        else:
            self._hide_toolbar()

    def _show_toolbar(self):
        self.toolbar.setFixedSize(self.args.preferred_width, TOOLBAR_HEIGHT)

    def _hide_toolbar(self):
        self.toolbar.setFixedSize(self.args.preferred_width, 0)

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

    def _add_origin_action(self):
        self._origin_action = QtGui.QAction('Origin', self)
        self._origin_action.setCheckable(True)
        self._origin_action.setShortcut('Shift+o')
        self._origin_action.toggled.connect(self._toggled_origin)
        self._view_menu.addAction(self._origin_action)

    def _toggled_origin(self):
        self._scene.view_origin = self._origin_action.isChecked()

    def _add_follow_output_action(self):
        self._follow_action = QtGui.QAction('&Follow output', self)
        self._follow_action.setCheckable(True)
        self._follow_action.setChecked(True)
        self._follow_action.setShortcut('Ctrl+F')
        self._follow_action.toggled.connect(self._toggled_follow)
        self._view_menu.addAction(self._follow_action)

    def _toggled_follow(self):
        if self.following_output():
            self._scene.set_default_camera_orientation()

    def following_output(self):
        return self._follow_action.isChecked()

    def _add_assumed_focus_action(self):
        self.focus_action = QtGui.QAction("Assumed focus", self)
        self.focus_action.setCheckable(True)
        self.focus_action.setShortcut('Ctrl+G')
        self._view_menu.addAction(self.focus_action)

    def _add_floor_action(self):
        self._floor_action = QtGui.QAction("Floor", self)
        self._floor_action.setCheckable(True)
        self._floor_action.setChecked(self._scene.view_floor)
        self._floor_action.setShortcut("f")
        self._floor_action.toggled.connect(self._toggled_floor)
        self._view_menu.addAction(self._floor_action)

    def _toggled_floor(self):
        self._scene.view_floor = self._floor_action.isChecked()

    def _add_input_action(self):
        self._input_action = QtGui.QAction("Input", self)
        self._input_action.setCheckable(True)
        self._input_action.setChecked(self._scene.view_input)
        self._input_action.setShortcut("i")
        self._input_action.toggled.connect(self._toggled_input)
        self._view_menu.addAction(self._input_action)

    def _toggled_input(self):
        self._scene.view_input = self._input_action.isChecked()

    def _add_frame_count_action(self):
        self._frame_count_action = QtGui.QAction("Frame count", self)
        self._frame_count_action.setCheckable(True)
        self._frame_count_action.setChecked(self._scene.view_frame_count)
        self._frame_count_action.setShortcut("c")
        self._frame_count_action.toggled.connect(self._toggled_frame_count)
        self._view_menu.addAction(self._frame_count_action)

    def _toggled_frame_count(self):
        self._scene.view_frame_count = self._frame_count_action.isChecked()

    def _add_orientation_action(self):
        self.orientation_action = QtGui.QAction("Orientation", self)
        self.orientation_action.setCheckable(True)
        self.orientation_action.setShortcut("o")
        self._view_menu.addAction(self.orientation_action)

    def _create_color_scheme_menu(self):
        menu = self._menu_bar.addMenu("Color scheme")
        action_group = QtGui.QActionGroup(self, exclusive=True)
        self._color_scheme_menu_actions = {}
        index = 1
        for name, scheme in color_schemes.iteritems():
            action = QtGui.QAction(name, action_group)
            action.setData(name)
            action.setCheckable(True)
            action.setShortcut(str(index))
            action_group.addAction(action)
            self._color_scheme_menu_actions[name] = action
            index += 1
        action_group.triggered.connect(
            lambda: self._changed_color_scheme(action_group.checkedAction()))
        menu.addActions(action_group.actions())

    def _set_color_scheme(self, scheme_name, caused_by_menu=False):
        self.color_scheme = color_schemes[scheme_name]
        if not caused_by_menu:
            self._color_scheme_menu_actions[scheme_name].setChecked(True)

    def _changed_color_scheme(self, checked_action):
        scheme_name = str(checked_action.data().toString())
        self._set_color_scheme(scheme_name, caused_by_menu=True)

    def keyPressEvent(self, event):
        key = event.key()
        if key == QtCore.Qt.Key_Escape:
            if self._fullscreen_action.isChecked():
                self._fullscreen_action.toggle()
        else:            
            self._scene.keyPressEvent(event)
            QtGui.QWidget.keyPressEvent(self, event)

    def customEvent(self, custom_qt_event):
        custom_qt_event.callback()

    def _handle_input(self, event):
        self._scene.processed_input = event.content

    def _handle_output(self, event):
        self._scene.received_output(event.content)

    def _handle_io_blend(self, event):
        self._scene.received_io_blend(event.content)

    def _handle_frame_count(self, event):
        self._scene.frame_count = event.content
        
    def send_event(self, event):
        event.source = "PythonUI"
        self.client.send_event(event)

    def _update_enable_friction(self, event):
        self.toolbar.enable_friction_checkbox.setChecked(event.content)
        
        
class Layer:
    def __init__(self, rendering_function):
        self._rendering_function = rendering_function
        self._updated = False
        self._display_list_id = None

    def draw(self):
        if not self._updated:
            if self._display_list_id is None:
                self._display_list_id = glGenLists(1)
            glNewList(self._display_list_id, GL_COMPILE)
            self._rendering_function()
            glEndList()
            self._updated = True
        glCallList(self._display_list_id)

    def refresh(self):
        self._updated = False

class CustomQtEvent(QtCore.QEvent):
    EVENT_TYPE = QtCore.QEvent.Type(QtCore.QEvent.registerEventType())

    def __init__(self, callback):
        QtCore.QEvent.__init__(self, CustomQtEvent.EVENT_TYPE)
        self.callback = callback
