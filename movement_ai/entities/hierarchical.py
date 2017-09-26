from experiment import *
from angle_parameters import EulerTo3Vectors, EulerToQuaternion
from numpy import array, dot
from transformations import euler_matrix, quaternion_from_euler, euler_from_quaternion
import random
from physics import Constrainers
from feature_extraction import FeatureExtractor
import math

ASSUME_NO_TRANSLATIONAL_OFFSETS_IN_NON_ROOT = True

rotation_parametrizations = {
    "vectors": EulerTo3Vectors,
    "quaternion": EulerToQuaternion,
    }

class InterpolationState:
    IDLE = "IDLE"
    INITIALIZING = "INITIALIZING"
    IN_PROGRESS = "IN_PROGRESS"

class LinearInterpolator:
    def interpolate(self, r1, r2, amount):
        return r1 + amount * (r2 - r1)

linear_interpolator = LinearInterpolator()

class ZeroNormedQuaternion(Exception):
    pass
    
class StaticQuaternionsInterpolator:
    EPSILON = 1E-12

    def interpolate(self, q0, q1, amount, shortest_path=True):
        q0_norm = numpy.linalg.norm(q0)
        if q0_norm == 0:
            raise ZeroNormedQuaternion(
                "First quaternion is zero and cannot be normalized.")
        q0 /= q0_norm

        q1_norm = numpy.linalg.norm(q1)
        if q1_norm == 0:
            raise ZeroNormedQuaternion(
                "Second quaternion is zero and cannot be normalized.")
        q1 /= q1_norm
        
        ca = numpy.dot(q0, q1)
        if shortest_path and ca<0:
            ca = -ca
            neg_q1 = True
        else:            
            neg_q1 = False

        if ca>=1.0:
            o = 0.0
        elif ca<=-1.0:
            o = math.pi
        else:
            o = math.acos(ca)
        so = math.sin(o)

        if (abs(so)<self.EPSILON):
            return linear_interpolator.interpolate(q0, q1, amount)

        a = math.sin(o*(1.0-amount)) / so
        b = math.sin(o*amount) / so
        if neg_q1:
            return q0*a - q1*b
        else:
            return q0*a + q1*b

static_quaternions_interpolator = StaticQuaternionsInterpolator()

class Candidate:
    def __init__(self, quaternion, previous_quaternion):
        self.quaternion = quaternion
        if previous_quaternion is not None:
            self.angular_distance = self._angular_distance(quaternion, previous_quaternion)

    def _angular_distance(self, q0, q1):
        ca = numpy.dot(q0, q1)
        if ca<0:
            ca = -ca
        if ca>=1.0:
            o = 0.0
        else:
            o = math.acos(ca)
        so = math.sin(o)
        return abs(so)
        
class DynamicQuaternionsInterpolator:
    EPSILON = 1E-12
    
    def __init__(self, joint_name):
        self._previous_quaternion = None
        self._joint_name = joint_name
        self._max_angular_step = 1

    def set_max_angular_step(self, max_angular_step):
        self._max_angular_step = max_angular_step

    def interpolate(self, q0, q1, amount):
        candidates = self._get_candidates(q0, q1, amount)
        nearest_candidate = self._pick_nearest_candidate(candidates)
        if self._previous_quaternion is None or \
           nearest_candidate.angular_distance < self._max_angular_step:
            result = nearest_candidate.quaternion
        else:
            result = static_quaternions_interpolator.interpolate(
                self._previous_quaternion, nearest_candidate.quaternion, self._max_angular_step)
        self._previous_quaternion = result
        return result

    def _get_candidates(self, q0, q1, amount):
        q0_norm = numpy.linalg.norm(q0)
        if q0_norm == 0:
            raise ZeroNormedQuaternion(
                "First quaternion is zero and cannot be normalized.")
        q0 /= q0_norm

        q1_norm = numpy.linalg.norm(q1)
        if q1_norm == 0:
            raise ZeroNormedQuaternion(
                "Second quaternion is zero and cannot be normalized.")
        q1 /= q1_norm

        result = []
        ca = numpy.dot(q0, q1)
        if ca<0:
            result.append(self._get_candidate(q0, q1, amount, -ca, neg_q1=True))
        result.append(self._get_candidate(q0, q1, amount, ca, neg_q1=False))
        return result

    def _get_candidate(self, q0, q1, amount, ca, neg_q1):
        if ca>=1.0:
            o = 0.0
        else:
            o = math.acos(ca)
        so = math.sin(o)

        if (abs(so)<self.EPSILON):
            quaternion = linear_interpolator.interpolate(q0, q1, amount)
            return Candidate(quaternion, self._previous_quaternion)
        
        a = math.sin(o*(1.0-amount)) / so
        b = math.sin(o*amount) / so
        if neg_q1:
            quaternion = q0*a - q1*b
        else:
            quaternion = q0*a + q1*b
        return Candidate(quaternion, self._previous_quaternion)

    def _pick_nearest_candidate(self, candidates):
        if len(candidates) == 1 or self._previous_quaternion is None:
            return candidates[0]
        else:
            return min(candidates, key=lambda candidate: candidate.angular_distance)

class Entity(BaseEntity):
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("--rotation-parametrization", "-r",
                            choices=["vectors", "quaternion"])
        parser.add_argument("--naive-quaternion-interpolation", action="store_true")
        parser.add_argument("--max-angular-step", type=float, default=1.)
        parser.add_argument("--translate", action="store_true")
        parser.add_argument("--translation-weight", type=float, default=1.)
        parser.add_argument("--friction", action="store_true")
        parser.add_argument("--confinement", action="store_true")
        parser.add_argument("--pose-scale", type=float, default=.5)
        parser.add_argument("--random-slide", type=float, default=0.0)
        parser.add_argument("--circle-slide", action="store_true")
        parser.add_argument("--left-foot")
        parser.add_argument("--left-hand")
        parser.add_argument("--left-forearm")
        parser.add_argument("--left-shoulder")
        parser.add_argument("--left-knee")
        parser.add_argument("--left-hip")
        parser.add_argument("--right-foot")
        parser.add_argument("--right-hand")
        parser.add_argument("--right-forearm")
        parser.add_argument("--right-shoulder")
        parser.add_argument("--right-knee")
        parser.add_argument("--right-hip")
        parser.add_argument("--torso")
        parser.add_argument("--neck")
        parser.add_argument("--head")

    def __init__(self, *args, **kwargs):
        BaseEntity.__init__(self, *args, **kwargs)
        self.rotation_parametrization = rotation_parametrizations[
            self.args.rotation_parametrization]
        self._create_parameter_info_table()
        if self.z_up:
            self._vertical_axis = "z"
            self._coordinate_up = 2
        else:
            self._vertical_axis = "y"
            self._coordinate_up = 1
        self._max_angular_step = self.args.max_angular_step
        self._normalized_constrainers = self._create_constrainers()
        self._unnormalized_constrainers = self._create_constrainers()
        self.modified_root_vertical_orientation = None
        self._last_root_vertical_orientation = None
        self._rotation_interpolators = {}
        self._enable_friction = self.args.friction
        if hasattr(self.args, "enable_features") and self.args.enable_features:
            self.feature_extractor = FeatureExtractor(self._coordinate_up)

    def _create_constrainers(self):
        return Constrainers(
            self._coordinate_up,
            enable_friction=(self.args.friction and not (
                hasattr(self.args, "show_all_feature_matches") and self.args.show_all_feature_matches)),
            enable_floor=self.floor,
            enable_confinement=self.args.confinement,
            enable_random_slide=(self.args.random_slide > 0),
            random_slide=self.args.random_slide,
            enable_circle_slide=self.args.circle_slide)

    def reset_constrainers(self):
        self._normalized_constrainers.reset()
        self._unnormalized_constrainers.reset()

    def _create_parameter_info_table(self):
        self._parameter_info = []
        root_joint_definition = self.bvh_reader.get_hierarchy().get_root_joint_definition()
        self._extend_parameter_info_table_recurse(root_joint_definition)

    def _extend_parameter_info_table_recurse(self, joint_definition):
        if not joint_definition.has_parent and self.args.translate:
            self._parameter_info.extend(
                [{"category": "translate", "component": "X"},
                 {"category": "translate", "component": "Y"},
                 {"category": "translate", "component": "Z"}])
        if joint_definition.has_rotation and not joint_definition.has_static_rotation:
            for n in range(self.rotation_parametrization.num_parameters):
                self._parameter_info.append({"category": joint_definition.name, "component": str(n)})
        for child_definition in joint_definition.child_definitions:
            self._extend_parameter_info_table_recurse(child_definition)

    def parameter_info(self, index):
        return self._parameter_info[index]

    def get_value_length(self):
        return len(self._parameter_info)

    def get_value(self):
        self.bvh_reader.set_pose_from_time(self.pose, self._t * self.args.bvh_speed)
        return self._joint_to_parameters(self.pose.get_root_joint())

    def get_value_from_frame(self, frame, **kwargs):
        self.bvh_reader.set_pose_from_frame(self.pose, frame, **kwargs)
        return self._joint_to_parameters(self.pose.get_root_joint())
        
    def get_random_value(self):
        self.bvh_reader.set_pose_from_time(self.pose,
            random.uniform(0, self.bvh_reader.get_duration()))
        return self._joint_to_parameters(self.pose.get_root_joint())

    def get_duration(self):
        return self.bvh_reader.get_duration() / self.args.bvh_speed

    def _joint_to_parameters(self, root_joint):
        parameters = []
        self._add_joint_parameters_recurse(root_joint, parameters)
        return parameters

    def _add_joint_parameters_recurse(self, joint, parameters):
        if not joint.definition.has_parent and self.args.translate:
            self._add_joint_translation_parameters(joint, parameters)
        if joint.definition.has_rotation and not joint.definition.has_static_rotation:
            self._add_joint_rotation_parameters(joint, parameters)
        for child in joint.children:
            self._add_joint_parameters_recurse(child, parameters)

    def _add_joint_translation_parameters(self, joint, parameters):
        vertex = joint.get_vertex()
        normalized_vector = self.bvh_reader.normalize_vector(vertex)
        weighted_vector = self.args.translation_weight * normalized_vector
        parameters.extend(weighted_vector)

    def _add_joint_rotation_parameters(self, joint, parameters):
        rotation_parameters = self.rotation_parametrization.rotation_to_parameters(
            joint.rotation)
        parameters.extend(rotation_parameters)

    def process_input(self, parameters):
        return self._parameters_to_scaled_normalized_vertices(parameters)

    def process_output(self, parameters):
        return self._constrained_output_vertices(parameters)

    def process_io_blend(self, parameters):
        return self._constrained_output_vertices(parameters)
    
    def _constrained_output_vertices(self, parameters):
        vertices = self._parameters_to_scaled_normalized_vertices(parameters)
        vertices = self._normalized_constrainers.constrain(vertices)
        return vertices

    def _parameters_to_scaled_normalized_vertices(self, parameters):
        self._set_pose_from_parameters(parameters)
        root_joint = self.pose.get_root_joint()
        vertices = root_joint.get_vertices()
        normalized_vertices = [
            self.bvh_reader.normalize_vector_without_translation(vertex) * self.args.pose_scale
            for vertex in vertices]
        return normalized_vertices

    def _set_pose_from_parameters(self, parameters):
        self._parameters_to_joint_recurse(parameters, self.pose.get_root_joint())
        self.bvh_reader.get_hierarchy().update_pose_world_positions(self.pose)

    def _parameters_to_joint_recurse(self, parameters, joint, parameter_index=0):
        if not joint.definition.has_parent and self.args.translate:
            parameter_index = self._parameters_to_joint_translation(parameters, joint, parameter_index)

        if joint.definition.has_rotation and not joint.definition.has_static_rotation:
            parameter_index = self._parameters_to_joint_rotation(parameters, joint, parameter_index)

        for child in joint.children:
            parameter_index = self._parameters_to_joint_recurse(parameters, child, parameter_index)

        return parameter_index

    def _parameters_to_joint_translation(self, parameters, joint, parameter_index):
        weighted_vector = parameters[parameter_index:parameter_index+3]
        parameter_index += 3
        if self.args.translation_weight == 0:
            joint.translation = [0, 0, 0]
        else:
            normalized_vector = numpy.array(weighted_vector) / self.args.translation_weight
            joint.translation = self.bvh_reader.skeleton_scale_vector(normalized_vector)
        return parameter_index

    def _parameters_to_joint_rotation(self, parameters, joint, parameter_index):
        rotation_parameters = parameters[
            parameter_index:parameter_index+
            self.rotation_parametrization.num_parameters]
        parameter_index += self.rotation_parametrization.num_parameters
        radians = self.rotation_parametrization.parameters_to_rotation(
            rotation_parameters, joint.definition.axes)
        if joint.parent is None:
            radians = self._process_root_orientation(joint, radians)
        joint.angles = radians
        return parameter_index

    def _process_root_orientation(self, root_joint, radians):
        return self._process_vertical_axis(radians, root_joint.definition.axes)

    def _process_vertical_axis(self, euler_angles, axes):
        if axes[1] == self._vertical_axis:
            return self._process_vertical_orientation_as_first_axis(euler_angles)
        else:
            if self._vertical_axis == "y":
                axes_with_vertical_first = "ryxz"
            elif self._vertical_axis == "z":
                axes_with_vertical_first = "rzxy"
            euler_angles_vertical_axis_first = euler_from_quaternion(
                quaternion_from_euler(*euler_angles, axes=axes),
                axes=axes_with_vertical_first)
            euler_angles_vertical_axis_first_reoriented = \
                self._process_vertical_orientation_as_first_axis(
                euler_angles_vertical_axis_first)
            return euler_from_quaternion(
                quaternion_from_euler(
                    *euler_angles_vertical_axis_first_reoriented,
                     axes=axes_with_vertical_first),
                axes=axes)

    def _process_vertical_orientation_as_first_axis(self, euler_angles):
        euler_angles = list(euler_angles)
        self._last_root_vertical_orientation = euler_angles[0]
        if self.modified_root_vertical_orientation is not None:
            euler_angles[0] = self.modified_root_vertical_orientation
        return euler_angles

    def get_last_root_vertical_orientation(self):
        return self._last_root_vertical_orientation

    def parameters_to_processed_pose(self, parameters, output_pose):
        self._set_pose_from_parameters(parameters)
        root_joint = self.pose.get_root_joint()
        vertices = root_joint.get_vertices()
        vertices =  self._unnormalized_constrainers.constrain(vertices)
        self.bvh_reader.get_hierarchy().set_pose_vertices(
            output_pose, vertices, not ASSUME_NO_TRANSLATIONAL_OFFSETS_IN_NON_ROOT)

    def extract_features(self, pose):
        positions = [
            pose.get_joint(getattr(self.args, joint_name)).worldpos
            for joint_name in self.feature_extractor.INPUT_JOINTS]
        return self.feature_extractor.extract_features(*positions)

    def interpolate(self, parameters1, parameters2, amount):
        result = []
        self._interpolate_recurse(
            parameters1, parameters2, amount, self.pose.get_root_joint(), result)
        return result
        
    def _interpolate_recurse(self, parameters1, parameters2, amount, joint, result, parameter_index=0):
        if not joint.definition.has_parent and self.args.translate:
            interpolated_translation, parameter_index = self._interpolate_translation(
                parameters1, parameters2, amount, joint, parameter_index)
            result += interpolated_translation

        if joint.definition.has_rotation and not joint.definition.has_static_rotation:
            interpolated_rotation, parameter_index = self._interpolate_rotation(
                parameters1, parameters2, amount, joint, parameter_index)
            result += interpolated_rotation

        for child in joint.children:
            parameter_index = self._interpolate_recurse(
                parameters1, parameters2, amount, child, result, parameter_index)

        return parameter_index

    def _interpolate_translation(self, parameters1, parameters2, amount, joint, parameter_index):
        vector1 = parameters1[parameter_index:parameter_index+3]
        vector2 = parameters2[parameter_index:parameter_index+3]
        parameter_index += 3
        result = list(numpy.array(vector2) * amount + numpy.array(vector1) * (1-amount))
        return result, parameter_index

    def _interpolate_rotation(self, parameters1, parameters2, amount, joint, parameter_index):        
        rotation_params1 = numpy.array(parameters1[
            parameter_index:parameter_index + self.rotation_parametrization.num_parameters])
        rotation_params2 = numpy.array(parameters2[
            parameter_index:parameter_index + self.rotation_parametrization.num_parameters])
        parameter_index += self.rotation_parametrization.num_parameters
        interpolator = self._get_rotation_interpolator(joint, rotation_params1, rotation_params2)
        try:
            result = list(interpolator.interpolate(rotation_params1, rotation_params2, amount))
        except ZeroNormedQuaternion as exception:
            print "WARNING: %s (joint: %s)" % (exception, joint.definition.name)
            result = rotation_params1
        return result, parameter_index

    def _get_rotation_interpolator(self, joint, r1, r2):
        if self.rotation_parametrization == EulerToQuaternion:
            return self._get_quaternion_interpolator(joint, r1, r2)
        else:
            return linear_interpolator

    def _get_quaternion_interpolator(self, joint, r1, r2):
        if self.args.naive_quaternion_interpolation:
            return static_quaternions_interpolator
        else:
            joint_index = joint.definition.index
            if joint_index not in self._rotation_interpolators:
                interpolator = DynamicQuaternionsInterpolator(joint.definition.name)
                interpolator.set_max_angular_step(self._max_angular_step)
                self._rotation_interpolators[joint_index] = interpolator
            return self._rotation_interpolators[joint_index]
        
    def set_friction(self, enable_friction):
        self._enable_friction = enable_friction
        self._normalized_constrainers.set_friction(enable_friction)
        self._unnormalized_constrainers.set_friction(enable_friction)
        
    def get_friction(self):
        return self._enable_friction

    def set_confinement(self, enable_confinement):
        self._normalized_constrainers.set_confinement(enable_confinement)
        self._unnormalized_constrainers.set_confinement(enable_confinement)

    def set_confinement_rate(self, rate):
        self._normalized_constrainers.set_confinement_rate(rate)
        self._unnormalized_constrainers.set_confinement_rate(rate)
        
    def set_max_angular_step(self, max_angular_step):
        self._max_angular_step = max_angular_step
        for interpolator in self._rotation_interpolators.values():
            interpolator.set_max_angular_step(max_angular_step)
