import numpy
from flaneur import Flaneur
from flaneur_behavior import FlaneurParameters
from imitate import Imitate, ImitateParameters, THRESHOLD_DISTANCE_TO_TARGET
from event import Event
from parameters import *
from interpolation import linear_interpolation
from dimensionality_reduction.utils import PositionComparison
import math
import copy
from dimensionality_reduction.behavior import Behavior

IDLE_IMITATION = 0.5
IDLE_TARGET_FEATURES = numpy.array([0, 0, 0, 0, 0])

THRESHOLD_FOR_IMITATING_ORIENTATION = 0.5
IMITATE = "imitate"
DONT_IMITATE = "dont_imitate"
ORIENTATION_DIFFERENCE_THRESHOLD = math.pi / 16

# IDLE_FLANEUR_PARAMETERS = {
#     "translational_speed": 0.01,
#     "directional_speed": 1.1,
#     "look_ahead_distance": 0.2,
# }
IDLE_FLANEUR_PARAMETERS = {
    "translational_speed": 0.01,
    "directional_speed": 1.1,
    "look_ahead_distance": 0.2,
}

ACTIVE_FLANEUR_PARAMETERS = {
    "translational_speed": 0.6,
    "directional_speed": 1.1,
    "look_ahead_distance": 0.2,
}

class HybridParameters(Parameters):
    def __init__(self):
        Parameters.__init__(self)
        self.add_parameter("imitation", type=float, default=1.,
                           choices=ParameterFloatRange(0., 1.))
        self._add_imitate_parameters()
        self._add_flaneur_parameters()

    def _add_imitate_parameters(self):
        for imitate_parameter in ImitateParameters():
            hybrid_parameter = self.add_parameter(
                imitate_parameter.name,
                imitate_parameter.type,
                imitate_parameter.default,
                imitate_parameter.choices)
            hybrid_parameter.imitate_parameter_name = imitate_parameter.name

    def _add_flaneur_parameters(self):
        for flaneur_parameter in FlaneurParameters():
            hybrid_parameter = self.add_parameter(
                "flaneur_%s" % flaneur_parameter.name,
                flaneur_parameter.type,
                flaneur_parameter.default,
                flaneur_parameter.choices)
            hybrid_parameter.flaneur_parameter_name = flaneur_parameter.name

class Hybrid(Behavior):
    def __init__(self,
                 student,
                 entity,
                 feature_matcher,
                 sampled_reductions,
                 num_components,
                 normalized_observed_reductions,
                 parameters,
                 show_all_feature_matches):
        Behavior.__init__(self)
        self._student = student
        self._entity = entity
        self._num_components = num_components
        self._show_all_feature_matches = show_all_feature_matches
        self._parameters = parameters
        parameters.add_listener(self._parameter_changed)
        self._create_flaneur(normalized_observed_reductions)
        self._create_imitate(feature_matcher, sampled_reductions)
        n_dimensions = len(normalized_observed_reductions[0])
        self._position = None
        self._direction = None
        self._orientation_state = None
        self.handle_user_intensity(None)

    def set_normalized_observed_reductions(self, normalized_observed_reductions):
        self._flaneur.set_normalized_observed_reductions(normalized_observed_reductions)

    def _parameter_changed(self, hybrid_parameter):
        if hasattr(hybrid_parameter, "flaneur_parameter_name"):
            flaneur_parameter = self._flaneur_parameters.get_parameter(
                hybrid_parameter.flaneur_parameter_name)
            flaneur_parameter.set_value(hybrid_parameter.value())
        elif hasattr(hybrid_parameter, "imitate_parameter_name"):
            imitate_parameter = self._imitate_parameters.get_parameter(
                hybrid_parameter.imitate_parameter_name)
            imitate_parameter.set_value(hybrid_parameter.value())

    def _create_flaneur(self, map_points):
        self._flaneur_parameters = FlaneurParameters()
        self._flaneur_parameters.add_listener(self._flaneur_parameter_changed)
        self._flaneur = Flaneur(map_points)

    def _flaneur_parameter_changed(self, parameter):
        self._update_flaneur_from_parameter(parameter)

    def _update_flaneur_from_parameter(self, parameter):
        setattr(self._flaneur, parameter.name, parameter.value())

    def _create_imitate(self, feature_matcher, sampled_reductions):
        self._imitate_parameters = ImitateParameters()
        self._imitate = Imitate(
            self._student,
            self._entity,
            feature_matcher,
            sampled_reductions,
            self._num_components,
            self._imitate_parameters,
            self._show_all_feature_matches)

    def proceed(self, time_increment):
        self._time_increment = time_increment
        if self._position is None:
            self._position = copy.copy(self._imitate.get_target_position())
        self._process_direction()
        if self._parameters.imitation < 0.99 or self._distance_to_target > THRESHOLD_DISTANCE_TO_TARGET:
            self._move_in_direction()
        self.notify(Event(Event.NEIGHBORS_CENTER, self._flaneur.get_neighbors_center()))

    def _process_direction(self):
        target_position = self._get_target_position()
        target_comparison = PositionComparison(
            source=self._position,
            target=target_position)
        self._distance_to_target = target_comparison.get_distance_to_target()
        if self._distance_to_target > 0:
            target_direction = target_comparison.get_direction_as_unit_vector()
            if self._direction is None:
                self._direction = target_direction
            else:
                self._move_towards_direction(target_direction)

    def _get_target_position(self):
        flaneur_target_position = self._flaneur.get_target_position(
            self._position, self._direction)
        self._imitate.set_reduction(self.get_reduction())
        imitate_target_position = self._imitate.get_target_position()
        if imitate_target_position is None:
            return flaneur_target_position
        else:
            return linear_interpolation(
                flaneur_target_position, imitate_target_position, self._parameters.imitation)

    def _move_towards_direction(self, target_direction):
        difference = target_direction - self._direction
        norm = numpy.linalg.norm(difference)
        if norm > 0:
            directional_speed = linear_interpolation(
                self._flaneur_parameters.directional_speed,
                self._imitate_parameters.imitation_directional_speed,
                self._parameters.imitation)
            self._direction += difference / norm * min(directional_speed * self._time_increment, 1)

    def _move_in_direction(self):
        norm = numpy.linalg.norm(self._direction)
        if norm > 0:
            translational_speed = linear_interpolation(
                self._flaneur_parameters.translational_speed,
                self._imitate_parameters.imitation_translational_speed,
                self._parameters.imitation)
            scaled_directional_vector = self._direction / norm * \
                min(self._time_increment * translational_speed, 1)
            scaled_directional_vector_norm = numpy.linalg.norm(
                scaled_directional_vector)
            if scaled_directional_vector_norm > self._distance_to_target:
                scaled_directional_vector *= self._distance_to_target / \
                    scaled_directional_vector_norm
            self._position += scaled_directional_vector

    def get_reduction(self):
        return self._student.unnormalize_reduction(self._position)

    def set_target_features(self, target_features):
        self._imitate.set_target_features(target_features)

    def handle_user_intensity(self, relative_intensity):
        if relative_intensity is None:
            # self._parameters.get_parameter("imitation").set_value(IDLE_IMITATION)
            self.set_target_features(IDLE_TARGET_FEATURES)
            # self._set_flaneur_parameters(IDLE_FLANEUR_PARAMETERS)
        # else:
        #     # imitation = 1 - math.pow(relative_intensity, 0.1)
        #     # self._parameters.get_parameter("imitation").set_value(imitation)
        #     self._set_flaneur_parameters(ACTIVE_FLANEUR_PARAMETERS)

    def _set_flaneur_parameters(self, parameters_dict):
        for name, value in parameters_dict.iteritems():
            self._parameters.get_parameter("flaneur_%s" % name).set_value(value)

    def get_root_vertical_orientation(self):
        self._process_orientation_state()
        if self._orientation_state == IMITATE:
            return self._target_root_vertical_orientation
        else:
            return None

    def _process_orientation_state(self):
        if self._orientation_state is None:
            if self._parameters.imitation > THRESHOLD_FOR_IMITATING_ORIENTATION:
                self._set_orientation_state(IMITATE)
            else:
                self._set_orientation_state(DONT_IMITATE)

        elif self._orientation_state == IMITATE and \
                self._parameters.imitation < THRESHOLD_FOR_IMITATING_ORIENTATION and \
                self._tracked_orientation_almost_equals_entity_orientation():
            self._set_orientation_state(DONT_IMITATE)

        elif self._orientation_state == DONT_IMITATE and \
                self._parameters.imitation >= THRESHOLD_FOR_IMITATING_ORIENTATION and \
                self._tracked_orientation_almost_equals_entity_orientation():
            self._set_orientation_state(IMITATE)

    def _set_orientation_state(self, new_state):
        print "orientation state %s => %s" % (self._orientation_state, new_state)
        self._orientation_state = new_state

    def _tracked_orientation_almost_equals_entity_orientation(self):
        entity_root_vertical_orientation = self._entity.get_last_root_vertical_orientation()
        return self._target_root_vertical_orientation is not None and \
            entity_root_vertical_orientation is not None and \
            abs(self._target_root_vertical_orientation - entity_root_vertical_orientation) < \
            ORIENTATION_DIFFERENCE_THRESHOLD
