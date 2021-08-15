from states import state_machine, MC
import random
import input_generator
from utils import random_unit_sphere_position
import math
from motion_durations import get_duration

PAUSE, MOVE = list(range(2))
PROBABILITY_TO_CENTER = 0.8

class Generator(input_generator.Generator):
    MC = state_machine.states[MC]

    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("-pause-duration", type=float, default=0.5)
        parser.add_argument("-fluctuation", type=float, default=0.2)
        parser.add_argument("-move-duration-fluctuation", type=float, default=0.2)

    def __init__(self, args):
        self._pause_duration = args.pause_duration
        self._fluctuation_magnitude = args.fluctuation
        self._move_duration_fluctuation = args.move_duration_fluctuation
        self._destination_state = self.MC
        self._destination_position = self._destination_state.position
        self._enter_pause_state()

    def update(self, time_increment):
        self._t += time_increment

        if self._state == PAUSE and self._t > self._pause_duration:
            self._enter_move_state()
        elif self._state == MOVE and self._t > self._move_duration:
            self._enter_pause_state()

    def _enter_pause_state(self):
        self._state = PAUSE
        self._source_state = self._destination_state
        self._source_position = self._destination_position
        self._t = 0.0

    def _enter_move_state(self):
        self._state = MOVE
        self._destination_state = self._select_destination()
        self._destination_position = self._destination_state.position + self._fluctuation()
        self._move_duration = get_duration(self._source_state, self._destination_state) * \
                              (1.0 + random.uniform(-self._move_duration_fluctuation,
                                                    +self._move_duration_fluctuation))
        print("%s -> %s" % (self._source_state.name, self._destination_state.name))
        distance = (self._destination_position - self._source_state.position).mag()
        self._t = 0.0

    def _select_destination(self):
        choices = self._source_state.outputs + self._source_state.inputs
        if self.MC in choices and random.random() < PROBABILITY_TO_CENTER:
            return self.MC
        else:
            return random.choice(choices)

    def position(self):
        if self._state == PAUSE:
            return self._source_position
        elif self._state == MOVE:
            return self._source_position + (self._destination_position - self._source_position) * \
                self._sigmoid(self._t / self._move_duration)

    def _sigmoid(self, x):
        return 1 - (math.cos(x * math.pi) + 1) / 2

    def _fluctuation(self):
        return random_unit_sphere_position() * self._fluctuation_magnitude
