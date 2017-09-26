import numpy
import random
import math

class FrictionConstrainer:
    def __init__(self, balance_detector):
        self._balance_detector = balance_detector
        self.enabled = True
        self.reset()

    def reset(self):
        self._translation = None
        self._supporting_vertex_index = None

    def constrain(self, vertices):
        self._update_translation(vertices)
        result = [vertex + self._translation for vertex in vertices]
        
        new_supporting_vertex_index = self._balance_detector.identify_supporting_vertex(vertices)
        if new_supporting_vertex_index != self._supporting_vertex_index:
            self._supporting_vertex_index = new_supporting_vertex_index
            self._supporting_vertex_locked_position = result[self._supporting_vertex_index]

        return result

    def _update_translation(self, vertices):
        if self._translation is None:
            num_dimensions = len(vertices[0])
            self._translation = [0] * num_dimensions
        elif self.enabled:
            self._translation = self._translation_wrt_supporting_vertex(vertices)
    
    def _translation_wrt_supporting_vertex(self, unconstrained_vertices):
        unconstrained_supporting_vertex = unconstrained_vertices[self._supporting_vertex_index]
        return self._supporting_vertex_locked_position - unconstrained_supporting_vertex

class BalanceDetector:
    def __init__(self, coordinate_up=1):
        self._coordinate_up = coordinate_up

    def identify_supporting_vertex(self, vertices):
        return self._lowest_vertex(vertices)

    def _lowest_vertex(self, vertices):
        return min(
            range(len(vertices)),
            key=lambda index: vertices[index][self._coordinate_up])
        
class FloorConstrainer:
    def __init__(self, coordinate_up=1):
        self._floor_y = 0
        self._coordinate_up = coordinate_up

    def constrain(self, vertices):
        bottom_y = min([vertex[self._coordinate_up] for vertex in vertices])
        offset = numpy.zeros(len(vertices[0]))
        offset[self._coordinate_up] = self._floor_y - bottom_y
        return [vertex + offset for vertex in vertices]

class Confinement:
    def __init__(self, coordinate_up=1, update_rate=0.01):
        self._coordinate_up = coordinate_up
        self._target_position = numpy.zeros(3)
        self._update_rate = update_rate
        self.enabled = True
        self.reset()

    def set_update_rate(self, rate):
        self._update_rate = rate
        
    def reset(self):
        self._translation = None

    def constrain(self, vertices):
        if not self.enabled:
            return vertices
        self._update_translation(vertices)
        result = [vertex + self._translation for vertex in vertices]
        return result

    def _update_translation(self, vertices):
        desired_translation = -vertices[0]
        desired_translation[self._coordinate_up] = 0
        if self._translation is None:
            self._translation = desired_translation
        else:
            self._translation += (desired_translation - self._translation) * self._update_rate
            
class RandomSlide:
    def __init__(self, speed):
        angle = random.uniform(0, math.pi*2)
        self._translation_increment = numpy.array(
            [math.cos(angle), 0, math.sin(angle)]) * speed
        self._translation = numpy.zeros(3)

    def constrain(self, vertices):
        self._translation += self._translation_increment
        return [vertex + self._translation for vertex in vertices]

class CircleSlide:
    def __init__(self):
        self._angle = 0
        self._translation = numpy.zeros(3)

    def constrain(self, vertices):
        translation_increment = numpy.array(
            [math.cos(self._angle), 0, math.sin(self._angle)]) * 0.02
        self._translation += translation_increment
        self._angle += 0.01
        return [vertex + self._translation for vertex in vertices]

class Constrainers:
    def __init__(self,
                 coordinate_up,
                 enable_friction=False,
                 enable_floor=False,
                 enable_confinement=False,
                 enable_random_slide=False,
                 random_slide=0.0,
                 enable_circle_slide=False):
        self.enable_friction = enable_friction
        self.enable_floor = enable_floor
        self.enable_confinement = enable_confinement
        self.enable_random_slide = enable_random_slide
        self.enable_circle_slide = enable_circle_slide
        self._friction = FrictionConstrainer(BalanceDetector(coordinate_up))
        self._floor = FloorConstrainer(coordinate_up)
        self._confinement = Confinement(coordinate_up)
        self._random_slide = RandomSlide(random_slide)
        self._circle_slide = CircleSlide()

    def constrain(self, vertices):
        if self.enable_friction:
            vertices = self._friction.constrain(vertices)
        if self.enable_floor:
            vertices = self._floor.constrain(vertices)
        if self.enable_confinement:
            vertices = self._confinement.constrain(vertices)
        if self.enable_random_slide:
            vertices = self._random_slide.constrain(vertices)
        if self.enable_circle_slide:
            vertices = self._circle_slide.constrain(vertices)
        return vertices

    def set_friction(self, enable_friction):
        self._friction.enabled = enable_friction

    def reset(self):
        self._friction.reset()

    def set_confinement(self, enable_confinement):
        self._confinement.enabled = enable_confinement

    def set_confinement_rate(self, rate):
        self._confinement.set_update_rate(rate)
        
