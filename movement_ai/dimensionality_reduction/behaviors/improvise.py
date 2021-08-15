from parameters import *
from navigator import Navigator, PathFollower
import interpolation
import dynamics as dynamics_module
import numpy
from dimensionality_reduction.behavior import Behavior

# WAITING_PARAMETERS = {
#     "velocity": 0.6,
#     "novelty": 0.3,
#     "extension": 1.0,
#     "location_preference": 0.5,
# }

PASSIVE_PARAMETERS = {
    "velocity": 0.3,
    "novelty": 0.03,
    "extension": 0.02,
    "location_preference": 1.0,
    "factor": 1.,
}

WAITING_PARAMETERS = PASSIVE_PARAMETERS

INTENSE_PARAMETERS = {
    "velocity": 1.0,
    "novelty": 1.0,
    "extension": 2.0,
    "location_preference": 0.0,
    "factor": 1.,
}

class ImproviseParameters(Parameters):
    def __init__(self):
        Parameters.__init__(self)
        self.add_parameter("novelty", type=float, default=.5,
                           choices=ParameterFloatRange(0., 1.))
        self.add_parameter("extension", type=float, default=1.,
                           choices=ParameterFloatRange(0., 2.))
        self.add_parameter("num_segments", type=int, default=10)
        self.add_parameter("resolution", type=int, default=100)
        self.add_parameter("velocity", type=float, default=0.5,
                           choices=ParameterFloatRange(.001, 3.))
        self.add_parameter("min_relative_velocity", type=float, default=.3,
                           choices=ParameterFloatRange(.001, 1.))
        self.add_parameter("dynamics", choices=["constant", "sine", "exponential"], default="sine")
        self.add_parameter("location_preference", type=float, default=0,
                           choices=ParameterFloatRange(0., 1.))
        self.add_parameter("factor", type=float, default=1,
                           choices=ParameterFloatRange(1., 10.))

class Improvise(Behavior):
    def __init__(self, student, num_components, params, preferred_location, max_novelty, on_changed_path=None):
        Behavior.__init__(self)
        self._student = student
        self._num_components = num_components
        self.params = params
        self._preferred_location = preferred_location
        self._max_novelty = max_novelty
        self._path = None
        self._path_follower = None
        self._on_changed_path = on_changed_path
        self._navigator = Navigator(
            map_points=student.normalized_observed_reductions)
        if preferred_location is not None:
            self._navigator.set_preferred_location(preferred_location)
        self._unadjusted_reduction = None
        self._reduction = None

    def set_normalized_observed_reductions(self, normalized_observed_reductions):
        self._navigator.set_map_points(normalized_observed_reductions)
        
    def select_next_move(self):
        found_non_empty_path = False
        while not found_non_empty_path:
            path_segments = self._generate_path()
            self._path = self._interpolate_path(path_segments)
            if len(self._path) > 0:
                found_non_empty_path = True
        self._path_follower = self._create_path_follower(self._path)
        if self._on_changed_path:
            self._on_changed_path()

    def _generate_path(self):
        while True:
            path = self._generate_potentially_empty_path()
            if len(path) > 0:
                return path

    def _generate_potentially_empty_path(self):
        return self._navigator.generate_path(
            departure = self._departure(),
            num_segments = self.params.num_segments,
            novelty = self.params.novelty * self._max_novelty,
            extension = self.params.extension,
            location_preference = self.params.location_preference)

    def _departure(self):
        if self._unadjusted_reduction is None:
            if self._preferred_location is not None:
                return self._preferred_location
            else:
                normalized_departure = numpy.array([.5] * self._num_components)
                return normalized_departure
        else:
            unnormalized_departure = self._unadjusted_reduction
            return self._student.normalize_reduction(unnormalized_departure)

    def _interpolate_path(self, path_segments):
        return interpolation.interpolate(
            path_segments,
            resolution=self.params.resolution)

    def _create_path_follower(self, path):
        dynamics_class = getattr(dynamics_module, "%s_dynamics" % self.params.dynamics)
        dynamics = dynamics_class(min_relative_velocity=self.params.min_relative_velocity)
        return PathFollower(path, dynamics)

    def proceed(self, time_increment):
        if self._path_follower is None:
            self.select_next_move()
        if self._path_follower.reached_destination():
            self.select_next_move()
        self._path_follower.proceed(time_increment * self.params.velocity)
        unadjusted_normalized_position = self._path_follower.current_position()
        self._unadjusted_reduction = self._student.unnormalize_reduction(unadjusted_normalized_position)
        normalized_position = (unadjusted_normalized_position - 0.5) * self.params.factor + 0.5
        self._reduction = self._student.unnormalize_reduction(normalized_position)

    def path(self):
        return self._path

    def handle_user_intensity(self, relative_intensity):
        if relative_intensity is None:
            parameters_to_set = WAITING_PARAMETERS
        else:
            parameters_to_set = self._interpolate_parameters(
                PASSIVE_PARAMETERS, INTENSE_PARAMETERS, relative_intensity)
        self._set_parameters(parameters_to_set)

    def _interpolate_parameters(self, low_parameters, high_parameters, interpolation_value):
        result = {}
        for name in ["velocity", "novelty", "extension", "location_preference"]:
            low_value = low_parameters[name]
            high_value = high_parameters[name]
            value = low_value + (high_value - low_value) * interpolation_value
            result[name] = value
        return result

    def _set_parameters(self, parameters_dict):
        for name, value in parameters_dict.items():
            self.params.get_parameter(name).set_value(value)
