import sys
import OpenGL
OpenGL.ERROR_LOGGING = "-check-opengl-errors" in sys.argv
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import argparse
import traceback_printer
from stopwatch import Stopwatch
from vector import Vector
import math
import collections
import sys
text_renderer_module = __import__("text_renderer")

ESCAPE = '\033'
CAMERA_POSITION = Vector(3, [-8, -0.5, -1.35])
CAMERA_Y_ORIENTATION = -88
CAMERA_X_ORIENTATION = 9

TEXT_RENDERERS = {
    "glut": "GlutTextRenderer",
    "ftgl": "FtglTextRenderer"
}

class Window:
    def __init__(self, args):
        self.args = args
        self.width = args.width
        self.height = args.height
        self.margin = args.margin
        self.show_fps = args.show_fps
        self.gl_display_mode = GLUT_RGBA | GLUT_DOUBLE | GLUT_DEPTH
        self._fullscreen = False
        self.exiting = False
        self._frames = []
        self.time_increment = 0
        self.stopwatch = Stopwatch()
        self._frame_count = 0
        self._set_camera_position(CAMERA_POSITION)
        self._set_camera_orientation(CAMERA_Y_ORIENTATION, CAMERA_X_ORIENTATION)
        self.fovy = 45
        self.near = 0.1
        self.far = 100.0
        self._text_renderer_class = getattr(text_renderer_module, TEXT_RENDERERS[args.text_renderer])

        if self.show_fps:
            self.fps_history = collections.deque(maxlen=10)
            self.previous_shown_fps_time = None

    def run(self):
        self.window_width = self.width + self.margin*2
        self.window_height = self.height + self.margin*2

        glutInit(sys.argv)

        if self.args.left is None:
            self._left = (glutGet(GLUT_SCREEN_WIDTH) - self.window_width) / 2
        else:
            self._left = self.args.left

        if self.args.top is None:
            self._top = (glutGet(GLUT_SCREEN_HEIGHT) - self.window_height) / 2
        else:
            self._top = self.args.top

        glutInitDisplayMode(self.gl_display_mode)
        glutInitWindowSize(self.window_width, self.window_height)
        self._non_fullscreen_window = glutCreateWindow("")
        glutDisplayFunc(self.DrawGLScene)
        glutIdleFunc(self.DrawGLScene)
        glutReshapeFunc(self.ReSizeGLScene)
        glutKeyboardFunc(self.keyPressed)
        self.InitGL()
        glutPositionWindow(self._left, self._top)

        if self.args.fullscreen:
            self._open_fullscreen_window()
            self._fullscreen = True

        self.ReSizeGLScene(self.window_width, self.window_height)
        glutMainLoop()

    def _open_fullscreen_window(self):
        glutGameModeString("%dx%d:32@75" % (self.window_width, self.window_height))
        glutEnterGameMode()
        glutSetCursor(GLUT_CURSOR_NONE)
        glutDisplayFunc(self.DrawGLScene)
        glutIdleFunc(self.DrawGLScene)
        glutReshapeFunc(self.ReSizeGLScene)
        glutKeyboardFunc(self.keyPressed)
        self.InitGL()
        glutPositionWindow(self._left, self._top)

    def InitGL(self):
        glClearColor(1.0, 1.0, 1.0, 0.0)
        glClearAccum(0.0, 0.0, 0.0, 0.0)
        glClearDepth(1.0)
        glShadeModel(GL_SMOOTH)

    def ReSizeGLScene(self, window_width, window_height):
        self.window_width = window_width
        self.window_height = window_height
        if window_height == 0:
            window_height = 1
        glViewport(0, 0, window_width, window_height)
        self.width = window_width - 2*self.margin
        self.height = window_height - 2*self.margin
        self._aspect_ratio = float(window_width) / window_height
        self.min_dimension = min(self.width, self.height)
        self.configure_2d_projection()
        self.resized_window()

    def resized_window(self):
        pass

    def configure_2d_projection(self):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0.0, self.window_width, self.window_height, 0.0, -1.0, 1.0)
        glMatrixMode(GL_MODELVIEW)

    def _set_camera_position(self, position):
        self._camera_position = position

    def _set_camera_orientation(self, y_orientation, x_orientation):
        self._camera_y_orientation = y_orientation
        self._camera_x_orientation = x_orientation

    def configure_3d_projection(self, pixdx=0, pixdy=0):
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
        glTranslatef(self._camera_position.x, self._camera_position.y, self._camera_position.z)

    def DrawGLScene(self):
        if self.exiting:
            glutDestroyWindow(glutGetWindow())
            return

        try:
            self._draw_gl_scene_error_handled()
        except Exception as error:
            traceback_printer.print_traceback()
            self.exiting = True
            raise error

    def _draw_gl_scene_error_handled(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        self.now = self.current_time()
        if self._frame_count == 0:
            self.stopwatch.start()
        else:
            self.time_increment = self.now - self.previous_frame_time
            self.configure_2d_projection()
            glTranslatef(self.margin, self.margin, 0)
            self._render_frames()
            self.render()
            if self.show_fps:
                self.update_fps_history()
                self.show_fps_if_timely()

        glutSwapBuffers()
        self.previous_frame_time = self.now
        self._frame_count += 1

    def current_time(self):
        return self.stopwatch.get_elapsed_time()

    def update_fps_history(self):
        if self.time_increment > 0:
            fps = 1.0 / self.time_increment
            self.fps_history.append(fps)

    def show_fps_if_timely(self):
        if self.previous_shown_fps_time:
            if (self.now - self.previous_shown_fps_time) > 1.0:
                self.calculate_and_show_fps()
        else:
            self.calculate_and_show_fps()

    def calculate_and_show_fps(self):
        print(sum(self.fps_history) / len(self.fps_history))
        self.previous_shown_fps_time = self.now

    def keyPressed(self, key, x, y):
        if key == ESCAPE:
            self.exiting = True
        elif key == 's':
            self._dump_screen()
        elif key == 'f':
            if self._fullscreen:
                glutSetCursor(GLUT_CURSOR_INHERIT)
                glutLeaveGameMode()
                glutSetWindow(self._non_fullscreen_window)
                self._fullscreen = False
            else:
                self._open_fullscreen_window()
                self._fullscreen = True

    def new_layer(self, rendering_function):
        layer = Layer(rendering_function, self.new_display_list_id())
        self._layers.append(layer)
        return layer

    def new_display_list_id(self):
        return glGenLists(1)

    def draw_text(self, text, size, x, y, z, font=None, spacing=None,
                  v_align="left", h_align="top"):
        if font is None:
            font = self.args.font
        self.text_renderer(text, size, font).render(x, y, z, v_align, h_align)

    def text_renderer(self, text, size, font=None):
        if font is None:
            font = self.args.font
        return self._text_renderer_class(self, text, size, font)

    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument('-width', dest='width', type=int, default=1024)
        parser.add_argument('-height', dest='height', type=int, default=768)
        parser.add_argument('-margin', dest='margin', type=int, default=0)
        parser.add_argument("-left", type=int)
        parser.add_argument("-top", type=int)
        parser.add_argument("-fullscreen", action="store_true")
        parser.add_argument('-show-fps', dest='show_fps', action='store_true')
        parser.add_argument("--text-renderer", choices=list(TEXT_RENDERERS.keys()), default="glut")
        parser.add_argument("--font", type=str)

    def add_frame(self, frame):
        self._frames.append(frame)

    def _render_frames(self):
        for frame in self._frames:
            frame.render_with_border()

class Frame:
    def __init__(self, window, left, top, width, height):
        self.window = window
        window.add_frame(self)
        self.left = left
        self.top = top
        self.width = width
        self.height = height

    def render_with_border(self):
        glColor3f(0,0,0)
        glPushMatrix()
        self._draw_border()
        self.render()
        glPopMatrix()

    def _draw_border(self):
        glTranslatef(self.left, self.top, 0)
        glBegin(GL_LINE_LOOP)
        glVertex2i(0, 0)
        glVertex2i(self.width, 0)
        glVertex2i(self.width, self.height)
        glVertex2i(0, self.height)
        glEnd()

    def render(self):
        pass

def run(visualizer_class, args):
    print("Hit ESC key to quit.")
    visualizer_class(args).run()
