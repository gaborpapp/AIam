import behaviour
import interpret
import random
from states import *
import motion_controller

SWAY_MAGNITUDE = 0.1
ENABLE_SWAYING = True

class Behaviour(behaviour.Behaviour):
    def __init__(self, *args):
        behaviour.Behaviour.__init__(self, *args)
        self.interpreter.add_callback(interpret.MOVE, self._move_observed)
        self.interpreter.add_callback(interpret.STATE, self._state_observed)
        self._last_observed_destination = None
        self._observed_state = self.MC

    # control logic

    def on_enabled(self):
        self.motion_controller.initiate_movement_to(InState(self.MC))

    def _state_observed(self, state):
        print("observed %r" % state)
        self._observed_state = state

    def process_input(self, input_position, time_increment):
        behaviour.Behaviour.process_input(self, input_position, time_increment)
        if self.motion_controller.get_mode() == motion_controller.IDLE:
            if self._in_sync():
                if ENABLE_SWAYING:
                    print("swaying")
                    self._idle()
            elif self._can_echo():
                print("echoing")
                self._echo()
            else:
                print("improvising")
                self._initiate_random_movement()

    def _in_sync(self):
        return self.motion_controller.state_nearest_to_cursor() == self._observed_state

    # echo

    def _can_echo(self):
        return self._last_observed_destination and \
            self.motion_controller.can_move_to(self._last_observed_destination)

    def _echo(self):
        self.motion_controller.initiate_movement_to(
            self._last_observed_destination,
            self._last_observed_duration)
        self._last_observed_destination = None

    def _move_observed(self, source_state, destination_state, duration):
        self._last_observed_destination = InState(destination_state)
        self._last_observed_duration = duration

    # improvise

    def _initiate_random_movement(self):
        cursor = self.motion_controller.get_cursor()
        if cursor.is_in_state():
            destination_state = random.choice(cursor.state.inputs + cursor.state.outputs)
        elif cursor.is_between_states():
            destination_state = random.choice([cursor.source_state, cursor.destination_state])
        self.motion_controller.initiate_movement_to(InState(destination_state))

    # idle

    def _idle(self):
        if self.motion_controller.get_cursor().is_in_state():
            self._initiate_sway_out()
        else:
            self._initiate_sway_in()

    def _initiate_sway_out(self):
        cursor = self.motion_controller.get_cursor()
        destination_state = random.choice(cursor.state.inputs + cursor.state.outputs)
        self.motion_controller.initiate_movement_to(
            BetweenStates(cursor.state, destination_state, SWAY_MAGNITUDE))

    def _initiate_sway_in(self):
        destination_state = self.motion_controller.state_nearest_to_cursor()
        self.motion_controller.initiate_movement_to(InState(destination_state))
