from states import state_machine, MC

class Behaviour:
    def __init__(self, interpreter, motion_controller):
        self.interpreter = interpreter
        self.motion_controller = motion_controller
        self.MC = state_machine.states[MC]
        self.enabled = True
        self._mode = None
        self._sub_behaviours = {}
        self._sub_behaviour = None

    def on_enabled(self):
        pass

    def process_input(self, input_position, time_increment):
        self._time_increment = time_increment
        if self._sub_behaviour:
            self._sub_behaviour.process_input(input_position, time_increment)

    def add_mode(self, module, *args):
        self._sub_behaviours[module] = module.Behaviour(*args)

    def get_mode(self):
        return self._mode

    def set_mode(self, module):
        if self._mode != module:
            print("-> %s" % module.__name__)
            self._mode = module
            self._sub_behaviour = self._sub_behaviours[module]
            for sub_behaviour in list(self._sub_behaviours.values()):
                sub_behaviour.enabled = (sub_behaviour == self._sub_behaviour)
            self._sub_behaviour.on_enabled()
