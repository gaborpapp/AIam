from vector import Vector3d
import collections

MC = "mc"
MLB = "mlb"
ML = "ml"
HB = "hb"
MB = "mb"
MLF = "mlf"
MRF = "mrf"
MRB = "mrb"
LLF = "llf"
HRF = "hrf"

class State:
    def __init__(self, name, output_names):
        self.name = name
        self.output_names = output_names
        self.outputs = []
        self.inputs = []

    def __eq__(self, other):
        try:
            return isinstance(other, State) and self.name == other.name
        except AttributeError:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "State(%r)" % (self.name)

class StateMachine:
    def __init__(self):
        self.states = collections.OrderedDict()
        self.transitions = []

    def add(self, name, output_names):
        assert name not in self.states
        self.states[name] = State(name, output_names)

    def compile(self):
        for input_name, input_state in self.states.items():
            for output_name in input_state.output_names:
                if output_name == input_name:
                    raise Exception("transition from %s to itself!" % input_name)
                output_state = self.states[output_name]
                input_state.outputs.append(output_state)
                self.transitions.append((input_state, output_state))
                if input_state not in output_state.inputs:
                    output_state.inputs.append(input_state)

    def cursor_to_euclidian_position(self, cursor):
        pos1 = cursor.source_state.position
        pos2 = cursor.destination_state.position
        return pos1 + (pos2 - pos1) * cursor.relative_position

    def set_config(self, config):
        for name, state in self.states.items():
            state.position = Vector3d(*config.states[name])

class Cursor:
    def is_in_state(self):
        return False

    def is_between_states(self):
        return False

class BetweenStates(Cursor):
    def __init__(self, source_state, destination_state, relative_position):
        self.source_state = source_state
        self.destination_state = destination_state
        self.relative_position = relative_position
        self.transition_length = (destination_state.position - source_state.position).mag()

    def is_between_states(self):
        return True

    def inter_state_position(self):
        return self.source_state.name, self.destination_state.name, self.relative_position

    def __repr__(self):
        return "BetweenStates(%r, %r, %r)" % (
            self.source_state.name, self.destination_state.name, self.relative_position)

    def __eq__(self, other):
        try:
            return isinstance(other, BetweenStates) and \
                other.inter_state_position() == self.inter_state_position()
        except AttributeError:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

class InState(Cursor):
    def __init__(self, state):
        self.state = state
        self._any_destination_state = None

    def _pick_any_destination_state(self):
        choices = self.state.inputs + self.state.outputs
        if len(choices) == 0:
            raise Exception("_pick_any_destination_state failed for %s as it has no inputs or outputs" % self.state)
        return choices[0]

    def is_in_state(self):
        return True

    def inter_state_position(self):
        if self._any_destination_state is None:
            self._any_destination_state = self._pick_any_destination_state()
        return self.state.name, self._any_destination_state.name, 0.0

    def __repr__(self):
        return "InState(%r)" % self.state.name

    def __eq__(self, other):
        try:
            return isinstance(other, InState) and other.state == self.state
        except AttributeError:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

state_machine = StateMachine()

state_machine.add(MC,  [MLB, ML , HB, MB, MLF])
state_machine.add(MLB, [MC,  ML,  HB, MB, MLF])
state_machine.add(ML,  [MLB, MLB, HB, MB, MLF])
state_machine.add(HB,  [MC,  MLB, ML, MB, MLF])
state_machine.add(MB,  [MC,  MLB, ML, HB, MLF])
state_machine.add(MLF, [MC,  MLB, ML, HB, MB])
state_machine.add(MRF, [])
state_machine.add(MRB, [])
state_machine.add(LLF, [])
state_machine.add(HRF, [])
state_machine.compile()

# state_machine.add(MC,  [MLB])
# state_machine.add(MLB, [])
# state_machine.compile()

# state_machine.add(MB,  [MRF])
# state_machine.add(MRF, [])
# state_machine.compile()
