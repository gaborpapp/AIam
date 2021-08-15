from .cuboid_scene import CuboidScene
from ui.ui import *
from transformations import euler_from_quaternion
import math

class Scene(CuboidScene):
    def draw_input(self, inp):
        self._draw_3dim_angle(inp)

    def draw_output(self, output):
        self._draw_3dim_angle(output)

    def _draw_3dim_angle(self, quaternion):
        x, y, z = euler_from_quaternion(quaternion, "rxyz")
        glRotatef(math.degrees(x), 1., 0., 0.)
        glRotatef(math.degrees(y), 0., 1., 0.)
        glRotatef(math.degrees(z), 0., 0., 1.)
        self.draw_cuboid_shape()
