import numpy
import math

class FeatureExtractor:
    FEATURES = [
        "left_hand_elevation",
        "right_hand_elevation",
        "head_elevation",
        "leaning",
        "knee_distance",
        "openness",
        "asymmetry",
    ]
    INPUT_JOINTS = [
        "left_foot",
        "left_hand",
        "left_forearm",
        "left_shoulder",
        "left_knee",
        "left_hip",
        "right_foot",
        "right_hand",
        "right_forearm",
        "right_shoulder",
        "right_knee",
        "right_hip",
        "torso",
        "neck",
        "head"]

    def __init__(self, coordinate_up=1):
        self._coordinate_up = coordinate_up
        self._horizontal_coordinates = list(set([0,1,2]) - set([coordinate_up]))
        self._feature_name_to_index = dict(
            (name, index)
            for name, index in zip(self.FEATURES, list(range(len(self.FEATURES)))))

    def get_num_features(self):
        return len(self.FEATURES)

    def extract_features(self,
                         left_foot_position,
                         left_hand_position,
                         left_forearm_position,
                         left_shoulder_position,
                         left_knee_position,
                         left_hip_position,
                         right_foot_position,
                         right_hand_position,
                         right_forearm_position,
                         right_shoulder_position,
                         right_knee_position,
                         right_hip_position,
                         torso_position,
                         neck_position,
                         head_position):
        left_arm_length = self._get_total_distance(
            [left_hand_position, left_forearm_position, left_shoulder_position, neck_position])
        left_hand_elevation = self._get_elevation(
            left_hand_position, neck_position, left_arm_length)

        right_arm_length = self._get_total_distance(
            [right_hand_position, right_forearm_position, right_shoulder_position, neck_position])
        right_hand_elevation = self._get_elevation(
            right_hand_position, neck_position, right_arm_length)

        torso_head_distance = self._get_total_distance(
            [torso_position, neck_position, head_position])
        head_elevation = self._get_elevation(
            torso_position, head_position, torso_head_distance)

        mid_feet_position = (left_foot_position + right_foot_position) / 2
        feet_neck_horizontal_distance = self._get_horizontal_distance(
            mid_feet_position, neck_position)
        max_feet_neck_horizontal_distance = self._get_total_distance(
            [left_foot_position, left_knee_position, left_hip_position, torso_position, neck_position])
        leaning = feet_neck_horizontal_distance / max_feet_neck_horizontal_distance

        max_knee_distance = self._get_total_distance(
            [left_knee_position, left_hip_position, right_hip_position, right_knee_position])
        knee_distance = self._distance(left_knee_position, right_knee_position)
        relative_knee_distance = knee_distance / max_knee_distance

        max_hand_distance = self._get_total_distance(
            [left_hand_position, left_forearm_position, left_shoulder_position,
             neck_position,
             right_shoulder_position, right_forearm_position, right_hand_position])
        hand_horizontal_distance = self._get_total_horizontal_distance(
            [left_hand_position, right_hand_position])
        openness = hand_horizontal_distance / max_hand_distance

        hand_vertical_distance = abs(
            left_hand_position[self._coordinate_up] - right_hand_position[self._coordinate_up])
        asymmetry = hand_vertical_distance / max_hand_distance

        return [
            left_hand_elevation,
            right_hand_elevation,
            head_elevation,
            leaning,
            relative_knee_distance,
            openness,
            asymmetry]

    def _get_total_distance(self, positions):
        return sum([self._distance(positions[i], positions[i+1])
                    for i in range(len(positions)-1)])

    def _get_elevation(self, start_position, end_position, total_distance):
        start_up = start_position[self._coordinate_up]
        end_up = end_position[self._coordinate_up]
        return ((start_up - end_up) / total_distance + 1) / 2

    def _distance(self, p1, p2):
        return numpy.linalg.norm(p1 - p2)

    def _get_horizontal_distance(self, position1, position2):
        return math.sqrt(sum([
                    pow(position1[coordinate] - position2[coordinate], 2)
                    for coordinate in self._horizontal_coordinates]))

    def _get_total_horizontal_distance(self, positions):
        return sum([self._get_horizontal_distance(positions[i], positions[i+1])
                    for i in range(len(positions)-1)])

    def get_feature_by_name(self, feature_values, feature_name):
        feature_index = self._feature_name_to_index[feature_name]
        return feature_values[feature_index]
