from vector import *
from states import state_machine, MC
import random
import math
import input_generator
from utils import random_unit_sphere_position

PAUSE, SWAY_OUT, SWAY_IN = list(range(3))

class Generator(input_generator.Generator):
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("-magnitude", type=float, default=0.5)
        parser.add_argument("-pause-duration", type=float, default=0.5)
        parser.add_argument("-sway-duration", type=float, default=1.0)
        parser.add_argument("-fluctuation", type=float, default=0.1)

    def __init__(self, args):
        self._magnitude = args.magnitude
        self._sway_duration = args.sway_duration
        self._pause_duration = args.pause_duration
        self._fluctuation_magnitude = args.fluctuation
        self._enter_sway_in_state()
        self._enter_pause_state()

    def update(self, time_increment):
        self._t += time_increment

        if self._state == PAUSE and self._t > self._pause_duration:
            self._enter_sway_out_state()
        elif self._state == SWAY_OUT and self._t > self._sway_duration:
            self._enter_sway_in_state()
        elif self._state == SWAY_IN and self._t > self._sway_duration:
            self._enter_pause_state()

    def _enter_pause_state(self):
        self._state = PAUSE
        self._t = 0

    def _enter_sway_out_state(self):
        self._state = SWAY_OUT
        self._t = 0
        self._sway_target = random_unit_sphere_position() * self._magnitude

    def _enter_sway_in_state(self):
        self._state = SWAY_IN
        self._t = 0
        self._source_position = state_machine.states[MC].position + self._fluctuation()

    def position(self):
        if self._state == PAUSE:
            return self._source_position
        elif self._state == SWAY_OUT:
            return self._source_position + (self._sway_target - self._source_position) * \
                self._sigmoid(self._t / self._sway_duration)
        elif self._state == SWAY_IN:
            return self._source_position + (self._sway_target - self._source_position) * \
                self._sigmoid((self._sway_duration - self._t) / self._sway_duration)

    def _sigmoid(self, x):
        return 1 - (math.cos(x * math.pi) + 1) / 2

    def _fluctuation(self):
        return random_unit_sphere_position() * self._fluctuation_magnitude
