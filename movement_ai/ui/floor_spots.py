import math
from OpenGL.GL import *
from .shader import Shader

FLOOR_SPOT_RADIUS = 1
FLOOR_GRID_SIZE = 9

class FloorSpots:
    def __init__(self, floor_color, background_color, y=0):
        self._floor_color = floor_color
        self._y = y
        self._display_list_id = None
        self._shader = Shader(
            radius = FLOOR_SPOT_RADIUS * 2 * FLOOR_GRID_SIZE * 1.5,
            background_color = background_color)

    def render(self, center_x, center_z, camera_x, camera_z):
        self._draw_floor_spots(
            center_x,
            center_z)
        self._shader.render(
            x=-camera_x,
            y=0,
            z=-camera_z)

    def _draw_floor_spots(self, center_x, center_z):
        cell_size = FLOOR_SPOT_RADIUS * 2
        quantified_center_x = int(center_x / cell_size / 2) * cell_size * 2
        quantified_center_z = int(center_z / cell_size) * cell_size
        for nx in range(FLOOR_GRID_SIZE):
            x = quantified_center_x + (nx - float(FLOOR_GRID_SIZE)/2 + 0.5) * cell_size
            if nx % 2 == 0:
                offset_z = 0
            else:
                offset_z = FLOOR_SPOT_RADIUS
            for nz in range(FLOOR_GRID_SIZE):
                z = offset_z + quantified_center_z + (nz - float(FLOOR_GRID_SIZE)/2 + 0.5) * cell_size
                self._draw_floor_spot(x=x, z=z)

    def _draw_floor_spot(self, x, z, y=0):
        if self._display_list_id is None:
            self._create_floor_spot_display_list()
        glPushMatrix()
        glTranslatef(x, y, z)
        glCallList(self._display_list_id)
        glPopMatrix()

    def _create_floor_spot_display_list(self, resolution=15):
        color_r, color_g, color_b, color_a = self._floor_color
        angle_increment = (float) (2 * math.pi / resolution);
        self._display_list_id = glGenLists(1)
        glNewList(self._display_list_id, GL_COMPILE)
        glBegin(GL_TRIANGLE_FAN)
        glColor4f(*self._floor_color)
        glVertex3f(0, 0, 0)
        glColor4f(color_r, color_g, color_b, 0)
        for i in range(resolution):
            angle1 = angle_increment * i
            angle2 = angle_increment * (i+1)
            glVertex3f(math.cos(angle1) * FLOOR_SPOT_RADIUS, 0, math.sin(angle1) * FLOOR_SPOT_RADIUS)
            glVertex3f(math.cos(angle2) * FLOOR_SPOT_RADIUS, 0, math.sin(angle2) * FLOOR_SPOT_RADIUS)
        glEnd()
        glEndList()
