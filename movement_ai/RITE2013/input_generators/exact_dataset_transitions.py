from states import *
import random
import input_generator

SPEED = 1.0

class Generator(input_generator.Generator):
    def __init__(self, args):
        self._destination_state = random.choice(list(state_machine.states.values()))
        self._t = 0.0
        self._transition_duration = 0

    def update(self, time_increment):
        self._t += time_increment
        if self._t > self._transition_duration:
            self._select_transition()
        self._inter_state_position.relative_position = self._t / self._transition_duration

    def _select_transition(self):
        self._source_state = self._destination_state
        self._destination_state = random.choice(self._source_state.outputs + self._source_state.inputs)
        print("%s -> %s" % (self._source_state.name, self._destination_state.name))
        self._inter_state_position = BetweenStates(self._source_state, self._destination_state, 0.0)
        distance = (self._destination_state.position - self._source_state.position).mag()
        self._transition_duration = distance / SPEED
        self._t = 0.0

    def position(self):
        return state_machine.cursor_to_euclidian_position(self._inter_state_position)
