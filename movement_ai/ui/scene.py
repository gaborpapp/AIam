from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from PyQt5 import QtCore, QtOpenGL
import math
import numpy

CIRCLE_PRECISION = 100

class Scene(QtOpenGL.QGLWidget):
    def __init__(self, parent, args, camera_y_speed, camera_key_speed, camera_drag_speed):
        self.args = args
        self._set_camera_from_arg(args.camera)
        self._camera_y_speed = camera_y_speed
        self._camera_key_speed = camera_key_speed
        self._camera_drag_speed = camera_drag_speed
        self._camera_translation = numpy.zeros(2)
        self._camera_movement = None
        self._dragging_orientation = False
        self._dragging_y_position = False
        QtOpenGL.QGLWidget.__init__(self, parent)
        self.setMouseTracking(True)

    def _set_camera_from_arg(self, arg):
        pos_x, pos_y, pos_z, orient_y, orient_z = list(map(float, arg.split(",")))
        self._set_camera_position([pos_x, pos_y, pos_z])
        self._set_camera_orientation(orient_y, orient_z)

    def set_default_camera_orientation(self):
        pos_x, pos_y, pos_z, orient_y, orient_z = list(map(float, self.args.camera.split(",")))
        self._set_camera_orientation(orient_y, orient_z)

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

    def configure_3d_projection(self, pixdx=0, pixdy=0, fovy=45, near=0.1, far=100.0):
        fov2 = ((fovy*math.pi) / 180.0) / 2.0
        top = near * math.tan(fov2)
        bottom = -top
        right = top * self._aspect_ratio
        left = -right
        xwsize = right - left
        ywsize = top - bottom
        dx = -(pixdx*xwsize/self.width)
        dy = -(pixdy*ywsize/self.height)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glFrustum (left + dx, right + dx, bottom + dy, top + dy, near, far)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        glRotatef(self._camera_x_orientation, 1.0, 0.0, 0.0)
        glRotatef(self._camera_y_orientation, 0.0, 1.0, 0.0)
        camera_translation = self.camera_translation()
        translate_x = self._camera_position[0] + camera_translation[0]
        translate_y = self._camera_position[1]
        translate_z = self._camera_position[2] + camera_translation[1]
        glTranslatef(translate_x, translate_y, translate_z)

    def configure_2d_projection(self, left, right, bottom, top):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(left, right, bottom, top, -1.0, 1.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def camera_translation(self):
        return self._camera_translation

    def _update_camera_translation(self):
        if self._camera_movement and self._camera_movement.is_active():
            self._camera_translation = self._camera_movement.translation()
            self._camera_movement.proceed(self.parent().time_increment)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and not self.following_output():
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
                self._camera_y_orientation + self._camera_drag_speed * (x - self._drag_x_previous),
                self._camera_x_orientation + self._camera_drag_speed * (y - self._drag_y_previous))
        elif self._dragging_y_position:
            self._camera_position[1] += self._camera_y_speed * (y - self._drag_y_previous)
        self._drag_x_previous = x
        self._drag_y_previous = y

    def print_camera_settings(self):
        print("%.3f,%.3f,%.3f,%.3f,%.3f" % (
            self._camera_position[0],
            self._camera_position[1],
            self._camera_position[2],
            self._camera_y_orientation, self._camera_x_orientation))

    def _set_camera_position(self, position):
        self._camera_position = position

    def _set_camera_orientation(self, y_orientation, x_orientation):
        self._camera_y_orientation = y_orientation
        self._camera_x_orientation = x_orientation

    def keyPressEvent(self, event):
        if not self.following_output():
            r = math.radians(self._camera_y_orientation)
            new_position = self._camera_position
            key = event.key()
            if key == QtCore.Qt.Key_A:
                new_position[0] += self._camera_key_speed * math.cos(r)
                new_position[2] += self._camera_key_speed * math.sin(r)
                self._set_camera_position(new_position)
                return True
            elif key == QtCore.Qt.Key_D:
                new_position[0] -= self._camera_key_speed * math.cos(r)
                new_position[2] -= self._camera_key_speed * math.sin(r)
                self._set_camera_position(new_position)
                return True
            elif key == QtCore.Qt.Key_W:
                new_position[0] += self._camera_key_speed * math.cos(r + math.pi/2)
                new_position[2] += self._camera_key_speed * math.sin(r + math.pi/2)
                self._set_camera_position(new_position)
                return True
            elif key == QtCore.Qt.Key_S:
                new_position[0] -= self._camera_key_speed * math.cos(r + math.pi/2)
                new_position[2] -= self._camera_key_speed * math.sin(r + math.pi/2)
                self._set_camera_position(new_position)
                return True

    def following_output(self):
        return False
    
    def draw_circle_on_floor(self, center_x, center_z, radius, y=0):
        glBegin(GL_LINE_STRIP)
        for i in range(CIRCLE_PRECISION):
            angle = math.pi * 2 * float(i) / (CIRCLE_PRECISION-1)
            x = center_x + radius * math.cos(angle)
            z = center_z + radius * math.sin(angle)
            glVertex3f(x, y, z)
        glEnd()

    def centralize_output(self, processed_output):
        self._camera_movement = CameraMovement(
            source=self._camera_translation,
            target=-self.get_root_vertex(processed_output))

    def get_root_vertex(self, processed_output):
        return numpy.zeros(2)

class CameraMovement:
    def __init__(self, source, target, duration=2):
        self._source = source
        self._target = target
        self._duration = duration
        self._t = 0
    
    def proceed(self, time_increment):
        self._t += time_increment

    def is_active(self):
        return self._t < self._duration

    def translation(self):
        return self._source + (self._target - self._source) * \
            self._velocity(self._t / self._duration)

    def _velocity(self, relative_t):
        return (math.sin((relative_t / 2 + .75) * math.pi*2) + 1) / 2
