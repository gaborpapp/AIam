import window
from vector import *
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from states import *
from simple_osc_receiver import OscReceiver
from argparse import ArgumentParser
from config_manager import load_config

MOUSE_REACTIVITY = 5.0
TORSO_COLOR = (0,0.5,1)
CENTER_OF_MASS_COLOR = (0.5,0,1)
INPUT_COLOR = (0,0,1)
OUTPUT_COLOR = (1,0,0)
OBSERVED_STATE_COLOR = (0,1,0)
TEXT_SIZE = 0.15

MIN_STATE_POINT_SIZE = 3.0
MAX_STATE_POINT_SIZE = 20.0

class Display(window.Window):
    def InitGL(self):
        window.Window.InitGL(self)
        glutMouseFunc(self._mouse_clicked)
        glutMotionFunc(self._mouse_moved)
        glEnable(GL_POINT_SMOOTH)
        glEnable(GL_LINE_SMOOTH)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self._y_orientation = 0.0
        self._x_orientation = 0.0

    def render(self):
        osc_receiver.serve()
        self._draw_input()
        self._draw_output()

    def _draw_output(self):
        glPushMatrix()
        self.configure_3d_projection(100, 0)
        glRotatef(self._x_orientation, 1.0, 0.0, 0.0)
        glRotatef(self._y_orientation, 0.0, 1.0, 0.0)
        self._draw_unit_cube()
        self._draw_transitions_as_lines()
        self._draw_states_as_points()
        self._draw_state_names()
        self._draw_input_position()
        self._draw_output_position()
        glPopMatrix()

    def _draw_states_as_points(self):
        for state in list(state_machine.states.values()):
            glPointSize(self._state_point_size(state))
            glBegin(GL_POINTS)
            # if state == observed_state:
            #     glColor3f(*OBSERVED_STATE_COLOR)
            # else:
            #     glColor3f(0,0,0)
            glColor3f(0,0,0)
            glVertex3f(*state.position)
            glEnd()

    def _state_point_size(self, state):
        if state.name in state_probability:
            probability = state_probability[state.name]
            return MIN_STATE_POINT_SIZE + (MAX_STATE_POINT_SIZE - MIN_STATE_POINT_SIZE) * \
                probability
        else:
            return MIN_STATE_POINT_SIZE

    def _draw_state_names(self):
        for state in list(state_machine.states.values()):
            if state == observed_state:
                glColor3f(*OBSERVED_STATE_COLOR)
            else:
                glColor3f(0,0,0)
            self.draw_text(state.name, TEXT_SIZE, *state.position)

    def _draw_transitions_as_lines(self):
        glColor4f(0,0,0,0.2)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        for input_state, output_state in state_machine.transitions:
            glVertex3f(*input_state.position)
            glVertex3f(*output_state.position)
        glEnd()

    def _draw_output_position(self):
        if output_cursor:
            output_position = state_machine.cursor_to_euclidian_position(output_cursor)
            self._draw_position(output_position, OUTPUT_COLOR)

    def _draw_input(self):
        glPushMatrix()
        self.configure_3d_projection(-300, 0)
        self._draw_unit_cube()
        self._draw_torso_position()
        self._draw_center_of_mass_position()
        glPopMatrix()

    def _draw_torso_position(self):
        self._draw_position(torso_position, TORSO_COLOR)

    def _draw_center_of_mass_position(self):
        self._draw_position(center_of_mass_position, CENTER_OF_MASS_COLOR)

    def _draw_input_position(self):
        self._draw_position(input_position, INPUT_COLOR)

    def _draw_position(self, position, color):
        if position is None:
            return
        glColor3f(*color)
        glPointSize(5.0)
        glBegin(GL_POINTS)
        glVertex3f(*position)
        glEnd()

    def _draw_unit_cube(self):
        glColor4f(0,0,0,0.2)
        glutWireCube(2.0)

    def _mouse_clicked(self, button, state, x, y):
        if button == GLUT_LEFT_BUTTON:
            self._dragging_orientation = (state == GLUT_DOWN)
        if state == GLUT_DOWN:
            self._drag_x_previous = x
            self._drag_y_previous = y

    def _mouse_moved(self, x, y):
        if self._dragging_orientation:
            self._y_orientation += x - self._drag_x_previous
            self._x_orientation -= y - self._drag_y_previous

def receive_torso_position(path, args, types, src, user_data):
    global torso_position
    position_tuple = args
    torso_position = Vector3d(*position_tuple)

def receive_center_of_mass_position(path, args, types, src, user_data):
    global center_of_mass_position
    position_tuple = args
    center_of_mass_position = Vector3d(*position_tuple)

def receive_input_position(path, args, types, src, user_data):
    global input_position
    position_tuple = args
    input_position = Vector3d(*position_tuple)

def receive_output_position(path, args, types, src, user_data):
    global output_cursor
    source_state_name, output_state_name, relative_position = args
    source_state = state_machine.states[source_state_name]
    output_state = state_machine.states[output_state_name]
    output_cursor = BetweenStates(
        source_state, output_state, relative_position)

def receive_observed_state(path, args, types, src, user_data):
    global observed_state
    observed_state_name = args[0]
    if observed_state_name:
        observed_state = state_machine.states[observed_state_name]
    else:
        observed_state = None

def receive_state_probability(path, args, types, src, user_data):
    global state_probability
    state_name, probability = args
    state_probability[state_name] = probability

torso_position = None
center_of_mass_position = None
input_position = None
observed_state = None
state_probability = {}
osc_receiver = OscReceiver(7892, listen="localhost")
osc_receiver.add_method("/normalized_torso_position", "fff", receive_torso_position)
osc_receiver.add_method("/normalized_center_of_mass_position", "fff", receive_center_of_mass_position)
osc_receiver.add_method("/input_position", "fff", receive_input_position)
osc_receiver.add_method("/position", "ssf", receive_output_position)
osc_receiver.add_method("/observed_state", "s", receive_observed_state)
osc_receiver.add_method("/state_probability", "sf", receive_state_probability)
osc_receiver.start()

output_cursor = None

parser = ArgumentParser()
parser.add_argument("-config", type=str)
window.Window.add_parser_arguments(parser)
args = parser.parse_args()
load_config(args.config)
window.run(Display, args)
