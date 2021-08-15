from .cuboid_scene import CuboidScene
from ui.ui import *
from expmap import *

class Scene(CuboidScene):
    def draw_input(self, inp):
        self._draw_expmap_rotation(inp)

    def draw_output(self, output):
        self._draw_expmap_rotation(output)

    def _draw_expmap_rotation(self, axis_angle_parameters):
        x, y, z = euler_from_expmap(axis_angle_parameters, "rxyz")
        glRotatef(math.degrees(x), 1., 0., 0.)
        glRotatef(math.degrees(y), 0., 1., 0.)
        glRotatef(math.degrees(z), 0., 0., 1.)
        self.draw_cuboid_shape()
