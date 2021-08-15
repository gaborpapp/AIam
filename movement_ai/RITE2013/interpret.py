from vector import *
from states import *
from sensory_adaptation import SensoryAdapter

SPATIAL_THRESHOLD = 0.5
TEMPORAL_THRESHOLD = 0.4
MIN_MOVE_DURATION = 2.0

MIN_DISTANCE = 0.001
MAX_DISTANCE = 0.5

MOVE, STATE, LEAVING_CENTER, ENTERING_CENTER, ACTIVITY = list(range(5))

SENSE_CENTER = False

if SENSE_CENTER:
    CENTER_SPATIAL_THRESHOLD = 0.04
    CENTER_TEMPORAL_THRESHOLD = 0.2
else:
    CENTER_SPATIAL_THRESHOLD = 0.15
    CENTER_TEMPORAL_THRESHOLD = 0.2

class PassivityDetector:
    def __init__(self, timeout, callback):
        self.timeout = timeout
        self.callback = callback
        self.passivity_duration = 0.0

    def process(self, state, time_increment):
        if state.name == MC:
            self.passivity_duration += time_increment
        else:
            self.passivity_duration = 0.0

        if self.passivity_duration > self.timeout:
            self.callback()
            self.passivity_duration = 0.0

class Interpreter:
    def __init__(self):
        self._state_hypothesis = None
        self._observed_state = None
        self._sensory_adapter = SensoryAdapter(0.1)
        self._in_center = True
        self._duration_in_center = 0
        self._time = 0.0
        self._callbacks = {
            MOVE: [],
            STATE: [],
            LEAVING_CENTER: [],
            ENTERING_CENTER: [],
            ACTIVITY: [],
        }
        self._passivity_detectors = []
        self.state_probability = {}

    def add_callback(self, event, callback):
        self._callbacks[event].append(callback)

    def add_passivity_callback(self, timeout, callback):
        self._passivity_detectors.append(PassivityDetector(timeout, callback))

    def process_input(self, input_position, time_increment):
        self._time += time_increment
        self._update_state_probabilities(input_position)
        self._detect_whether_leaving_or_entering_center(input_position, time_increment)
        self._detect_whether_state_changed(input_position, time_increment)
        self._process_passivity_detectors(time_increment)

    def _update_state_probabilities(self, input_position):
        for state_name, state in state_machine.states.items():
            distance = (state.position - input_position).mag()
            probability = 1 - (self._clamp(distance, MIN_DISTANCE, MAX_DISTANCE) - MIN_DISTANCE) / \
                 (MAX_DISTANCE - MIN_DISTANCE)
            self.state_probability[state_name] = probability

    def sensed_center(self):
        if SENSE_CENTER:
            return self._sensory_adapter.sensed_center()
        else:
            return state_machine.states[MC].position

    def guess_target_state(self, input_position, source_state):
        return min(
            source_state.inputs + source_state.outputs,
            key=lambda output_state: self._distance_to_transition(input_position, source_state, output_state))

    def _detect_whether_leaving_or_entering_center(self, input_position, time_increment):
        if SENSE_CENTER:
            sensed_input_position = self._sensory_adapter.process(
                input_position, time_increment)
        else:
            sensed_input_position = input_position
        input_in_center = sensed_input_position.mag() < CENTER_SPATIAL_THRESHOLD
        if self._in_center:
            if input_in_center:
                self._duration_in_center += time_increment
            else:
                if self._duration_in_center >= CENTER_TEMPORAL_THRESHOLD:
                    self._fire_callbacks(LEAVING_CENTER, input_position)
                    self._in_center = False
        else:
            if input_in_center:
                self._in_center = True
                self._duration_in_center = 0
                self._fire_callbacks(ENTERING_CENTER, input_position)

    def _detect_whether_state_changed(self, input_position, time_increment):
        self._input_position = input_position
        nearest_state = self._nearest_state()
        if nearest_state and \
           nearest_state != self._observed_state and \
           self._distance_to_state(nearest_state) < SPATIAL_THRESHOLD:
            if nearest_state == self._state_hypothesis:
                self._duration_in_state += time_increment
                if self._duration_in_state > TEMPORAL_THRESHOLD:
                    self._state_potentially_observed(nearest_state)
            else:
                self._state_hypothesis = nearest_state
                self._duration_in_state = 0

    def _nearest_state(self):
        return min(list(state_machine.states.values()),
                   key=lambda state: self._distance_to_state(state))

    def _distance_to_state(self, state):
        return (state.position - self._input_position).mag()

    def _state_potentially_observed(self, new_observed_state):
        if self._observed_state:
            duration = self._time - self._observed_state_at_time
            if duration > MIN_MOVE_DURATION:
                self._fire_callbacks(MOVE, self._observed_state, new_observed_state, duration)
                self._state_observed(new_observed_state)
        else:
            self._state_observed(new_observed_state)

    def _state_observed(self, new_observed_state):
        self._observed_state = new_observed_state
        self._observed_state_at_time = self._time
        self._fire_callbacks(STATE, new_observed_state)
        if new_observed_state.name != MC:
            self._fire_callbacks(ACTIVITY)

    def _fire_callbacks(self, event, *args):
        for callback in self._callbacks[event]:
            callback(*args)

    def _distance_to_transition(self, position, input_state, output_state):
        inter_state_position = self._perpendicular_inter_state_position(
            position, input_state, output_state)
        return (position -
                state_machine.cursor_to_euclidian_position(inter_state_position)).mag()

    def _perpendicular_inter_state_position(self, v, input_state, output_state):
        pos1 = input_state.position
        pos2 = output_state.position
        intersection = self._perpendicular(pos1, pos2, v)
        relative_position = (intersection - pos1).mag() / (pos2 - pos1).mag()
        relative_position = self._clamp(relative_position, 0, 1)
        return BetweenStates(input_state, output_state, relative_position)

    def _perpendicular(self, p1, p2, q):
        u = p2 - p1
        pq = q - p1
        w2 = pq - u * (dot_product(pq, u) / pow(u.mag(), 2))
        return q - w2

    def _clamp(self, v, v_min, v_max):
        return max(min(v, v_max), v_min)

    def _process_passivity_detectors(self, time_increment):
        if self._observed_state:
            for detector in self._passivity_detectors:
                detector.process(self._observed_state, time_increment)
