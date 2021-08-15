import math
from transformations import euler_matrix, euler_from_matrix
from .bvh import JointDefinition

AXIS_TO_CHANNEL = {
    "x": "Xrotation",
    "y": "Yrotation",
    "z": "Zrotation"
    }

def axes_to_channels(axes):
    return [AXIS_TO_CHANNEL[axis] for axis in axes]

class BvhProcessor:
    def convert_rotation_order_in_hierarchy(self, axes, hierarchy):
        self._set_joint_definition_rotation_order_recurse(hierarchy.get_root_joint_definition(), axes)
        
    def _set_joint_definition_rotation_order_recurse(self, joint_definition, axes):
        if joint_definition.has_rotation:
            joint_definition.axes = joint_definition.axes[0] + axes
            if joint_definition.channels[0:3] != ["Xposition", "Yposition", "Zposition"]:
                raise Exception("set_rotation_order expects that the first 3 channels are positions.")
            joint_definition.channels = joint_definition.channels[0:3] + axes_to_channels(axes)
        for child_definition in joint_definition.child_definitions:
            self._set_joint_definition_rotation_order_recurse(child_definition, axes)

    def convert_rotation_order_in_frame(self, axes, frame, input_hierarchy, output_hierarchy):
        result = []
        self._convert_rotation_order_in_frame_recurse(
            axes,
            frame,
            input_hierarchy.get_root_joint_definition(),
            output_hierarchy.get_root_joint_definition(),
            result)
        return result

    def _convert_rotation_order_in_frame_recurse(
            self, axes, frame, input_joint_definition, output_joint_definition, result, frame_data_index=0):
        input_joint_dict = dict()
        output_joint_dict = dict()
        for channel in input_joint_definition.channels:
            input_joint_dict[channel] = frame[frame_data_index]
            if channel in ["Xposition", "Yposition", "Zposition"]:
                output_joint_dict[channel] = frame[frame_data_index]
            frame_data_index += 1

        if input_joint_definition.has_rotation:
            output_axes = input_joint_definition.axes[0] + axes
            degrees_before_conversion = [
                input_joint_dict[channel] for channel in input_joint_definition.rotation_channels]
            angles_before_conversion = [math.radians(d) for d in degrees_before_conversion]
            angles_after_conversion = euler_from_matrix(
                euler_matrix(*angles_before_conversion, axes=input_joint_definition.axes),
                axes=output_axes)
            degrees_after_conversion = [math.degrees(r) for r in angles_after_conversion]
            angle_index = 0
            for channel in output_joint_definition.channels:
                if channel in ["Xrotation", "Yrotation", "Zrotation"]:
                    output_joint_dict[channel] = degrees_after_conversion[angle_index]
                    angle_index += 1

        for channel in output_joint_definition.channels:
            result.append(output_joint_dict[channel])

        for input_child_definition, output_child_definition in zip(
                input_joint_definition.child_definitions, output_joint_definition.child_definitions):
            frame_data_index = self._convert_rotation_order_in_frame_recurse(
                axes, frame, input_child_definition, output_child_definition, result, frame_data_index)
            if(frame_data_index == 0):
                raise Exception("fatal error")

        return frame_data_index

    def delete_joints_from_hierarchy(self, joints_to_delete, hierarchy):
        self._delete_joints_recurse(joints_to_delete, hierarchy.get_root_joint_definition())

    def _delete_joints_recurse(self, joints_to_delete, joint_definition):
        result_child_definitions = []
        for child_definition in joint_definition.child_definitions:
            if child_definition.name not in joints_to_delete:
                result_child_definitions.append(child_definition)
            self._delete_joints_recurse(joints_to_delete, child_definition)
        if len(result_child_definitions) == 0 and len(joint_definition.child_definitions) > 0:
            result_child_definitions.append(self._create_end_node())
        joint_definition.child_definitions = result_child_definitions

    def _create_end_node(self):
        joint_definition = JointDefinition(name="End Site", index=None, channels=[], is_end=True)
        joint_definition.offset = (0, 0, 0)
        return joint_definition

    def delete_joints_from_frame(self, hierarchy, joints_to_delete, frame):
        result = []
        self._delete_joints_from_frame_recurse(
            joints_to_delete, frame, hierarchy.get_root_joint_definition(), result)
        return result

    def _delete_joints_from_frame_recurse(self, joints_to_delete, frame, joint_definition, result, frame_data_index=0, skip_children=False):
        if joint_definition.name in joints_to_delete or skip_children:
            frame_data_index += len(joint_definition.channels)
            skip_children = True
        else:
            for channel in joint_definition.channels:
                result.append(frame[frame_data_index])
                frame_data_index += 1
            skip_children = False

        for child_definition in joint_definition.child_definitions:
            frame_data_index = self._delete_joints_from_frame_recurse(
                joints_to_delete, frame, child_definition, result, frame_data_index, skip_children)

        return frame_data_index
