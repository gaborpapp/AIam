# echo: Observe and repeat moves, one by one, like an echo.

import behaviour
import interpret

class Behaviour(behaviour.Behaviour):
    def __init__(self, *args):
        behaviour.Behaviour.__init__(self, *args)
        self.interpreter.add_callback(interpret.MOVE, self._move_observed)
        self._last_observed_destination_state = None

    def process_input(self, input_position, time_increment):
        behaviour.Behaviour.process_input(self, input_position, time_increment)
        if self._last_observed_destination_state and \
           self.motion_controller.can_move_to(self._last_observed_destination_state):
            self.motion_controller.initiate_movement_to(self._last_observed_destination_state)

    def _move_observed(self, source_state, destination_state, duration):
        self._last_observed_destination_state = destination_state
