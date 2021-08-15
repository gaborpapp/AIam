from OpenGL.GL import *
import math
from .shader import Shader

class FloorGrid:
    def __init__(self, num_cells, size, floor_color, background_color, y=0):
        self._num_cells = num_cells
        self._size = size
        self._floor_color = floor_color
        self._y = y
        self._cell_size = float(self._size) / self._num_cells
        self._hypotenuse = math.sqrt(self._cell_size * self._cell_size * 2)
        self._shader = Shader(
            radius = math.sqrt(self._size * self._size * 2),
            background_color = background_color)

    def render(self, center_x, center_z, camera_x, camera_z):
        self._draw_grid(center_x, center_z)
        self._shader.render(-camera_x, 0, -camera_z)

    def _draw_grid(self, center_x, center_z):
        z1 = - self._size/2
        z2 = + self._size/2
        x1 = - self._size/2
        x2 = + self._size/2

        glColor4f(*self._floor_color)
        glLineWidth(1.4)

        quantified_center_x = int(center_x / self._hypotenuse) * self._hypotenuse
        quantified_center_z = int(center_z / self._hypotenuse) * self._hypotenuse
        glPushMatrix()
        glTranslatef(quantified_center_x, 0, quantified_center_z)
        glRotatef(45, 0, 1, 0)

        for n in range(self._num_cells):
            glBegin(GL_LINES)
            x = x1 + float(n) * self._cell_size
            glVertex3f(x, self._y, z1)
            glVertex3f(x, self._y, z2)
            glEnd()

        for n in range(self._num_cells):
            glBegin(GL_LINES)
            z = z1 + float(n) * self._cell_size
            glVertex3f(x1, self._y, z)
            glVertex3f(x2, self._y, z)
            glEnd()

        glPopMatrix()
