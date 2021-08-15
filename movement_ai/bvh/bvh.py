# adopted from BVHplay (http://sourceforge.net/projects/bvhplay/)

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")

from numpy import array, dot
import numpy
from transformations import euler_matrix, euler_from_matrix

import math
from .geo import Euler, make_translation_matrix, edge

class JointDefinition:
    def __init__(self, name, index, is_end, channels=[]):
        self.name = name
        self.index = index
        self.is_end = is_end
        self.child_definitions = []
        self.channels = channels
        self.translation_matrix = array([
            [0.,0.,0.,0.],
            [0.,0.,0.,0.],
            [0.,0.,0.,0.],
            [0.,0.,0.,0.] ])
        self.has_parent = False
        self.parent = None
        self.has_rotation = False
        self.has_static_rotation = False

    def clone(self):
        result = JointDefinition(self.name, self.index, self.is_end, self.channels)
        result.offset = self.offset
        result.has_rotation = self.has_rotation
        if self.has_rotation:
            result.axes = self.axes
        result.child_definitions = []
        for child_definition in self.child_definitions:
            result.add_child_definition(child_definition.clone())
        return result
    
    def add_child_definition(self, child_definition):
        self.child_definitions.append(child_definition)
        child_definition.has_parent = True
        child_definition.parent = self

    def create_joint(self, parent=None):
        joint = Joint(self, parent)
        for child_definition in self.child_definitions:
            child = child_definition.create_joint(parent=joint)
            joint.add_child(child)
        return joint

    def populate_edges_from_vertices_recurse(self, vertices, edgelist):
        if self.has_parent:
            new_edge = edge(
              vertices[self.parent.index],
              vertices[self.index])
            edgelist.append(new_edge)

        for child_definition in self.child_definitions:
            child_definition.populate_edges_from_vertices_recurse(vertices, edgelist)

    def get_rotation_index(self, axis):
        return self.axes.index(axis) - 1 # skip leading "r" from e.g. "rxyz"

class Joint:
    def __init__(self, definition, parent=None):
        self.definition = definition
        self.parent = parent
        self.translation = array([0.,0.,0.])
        self.children = []
        if definition.has_static_rotation:
            self.angles = definition.static_angles

    def add_child(self, child):
        self.children.append(child)

    def get_vertex(self):
        return array([
            self.worldpos[0],
            self.worldpos[1],
            self.worldpos[2],
            1])

    def get_vertices(self):
        result = []
        self._add_vertices_recurse(result)
        return result

    def _add_vertices_recurse(self, vertices):
        vertices.append(self.get_vertex())
        for child in self.children:
            child._add_vertices_recurse(vertices)

    def Xposition(self):
        return self.worldpos[0]

    def Yposition(self):
        return self.worldpos[1]

    def Zposition(self):
        return self.worldpos[2]

    def Xrotation(self):
        return math.degrees(self.angles[self.definition.rotation_index["Xrotation"]])

    def Yrotation(self):
        return math.degrees(self.angles[self.definition.rotation_index["Yrotation"]])

    def Zrotation(self):
        return math.degrees(self.angles[self.definition.rotation_index["Zrotation"]])
    
    def set_vertices(self, vertices, recurse=True):
        if self.definition.is_end:
            # should not be needed if renderer ignores end nodes?
            self.worldpos = vertices[self.parent.definition.index]
        else:
            self.worldpos = vertices[self.definition.index]
            if recurse:
                for child in self.children:
                    child.set_vertices(vertices)

class Hierarchy:
    def __init__(self, root_node_definition):
        self._num_joints = 0
        self._joint_definitions = {}
        self._root_joint_definition = root_node_definition
        self._process_joint_definition(root_node_definition)

    def clone(self):
        return Hierarchy(self._root_joint_definition.clone())
    
    def _process_joint_definition(self, joint_definition):
        for child_definition in joint_definition.child_definitions:
            self._process_joint_definition(child_definition)
        self._joint_definitions[joint_definition.name] = joint_definition
        self._num_joints += 1

    def get_num_joints(self):
        return self._num_joints

    def create_pose(self):
        return Pose(self)

    def set_pose_vertices(self, pose, vertices=None, get_vertex=None):
        if vertices is None:
            if get_vertex is None:
                raise Exception("vertices or get_vertex must be specified")
            else:
                vertices = self._get_vertices(get_vertex)
        pose.get_root_joint().set_vertices(vertices)

    def _get_vertices(self, get_vertex):
        def _add_vertices_recurse(joint_definition, vertices):
            if not joint_definition.is_end:
                vertices[joint_definition.index] = get_vertex(joint_definition.name)
                for child_definition in joint_definition.child_definitions:
                    _add_vertices_recurse(child_definition, vertices)

        result = {}
        _add_vertices_recurse(self.get_root_joint_definition(), result)
        return result

    def update_pose_offsets_and_angles(self, pose):
        if not hasattr(self._root_joint_definition, "offset"):
            self._set_bvh_offset_recurse(pose, self._root_joint_definition)
        self._calculate_joint_angles_recurse(pose, pose.get_root_joint())

    def _set_bvh_offset_recurse(self, pose, joint_definition, parent=None):
        if parent is None or parent.parent is None:
            joint_definition.offset = (0, 0, 0)
        else:
            length = numpy.linalg.norm(
                pose.get_joint(parent.parent.name).worldpos - \
                    pose.get_joint(parent.name).worldpos)
            joint_definition.offset = (length, 0, 0)
        for child_definition in joint_definition.child_definitions:
            self._set_bvh_offset_recurse(pose, child_definition, joint_definition)

    def _calculate_joint_angles_recurse(self, pose, bvh_joint, parent=None, parent_rotation_matrix=None):
        if parent is None or parent.parent is None:
            bvh_joint.angles = (0.0, 0.0, 0.0)
        else:
            b = array(pose.get_joint(parent.parent.definition.name).worldpos[0:3])
            a = array(pose.get_joint(parent.definition.name).worldpos[0:3])
            direction = b - a
            direction /= numpy.linalg.norm(direction)
            heading = math.atan2(direction[1], direction[0])
            pitch = math.asin(direction[2])
            up = array([1, 0, 0])
            w0 = array([-direction[1], direction[0], 0])
            u0 = numpy.cross(w0, direction)
            bank = math.atan2(
                dot(w0, up),
                dot(u0, up) / numpy.linalg.norm(w0) * numpy.linalg.norm(u0))
            euler_angles = (heading, bank, pitch)
            this_rotation_matrix = euler_matrix(*euler_angles, axes="rxyz")
            if parent_rotation_matrix is not None:
                rotation_matrix = dot(parent_rotation_matrix, numpy.linalg.inv(this_rotation_matrix))
                euler_angles = euler_from_matrix(rotation_matrix, axes="rxyz")
                parent_rotation_matrix = dot(
                    parent_rotation_matrix, euler_matrix(*euler_angles, axes="rxyz"))
            else:
                parent_rotation_matrix = this_rotation_matrix
            parent.angles = euler_angles

        for bvh_child in bvh_joint.children:
            self._calculate_joint_angles_recurse(pose, bvh_child, bvh_joint, parent_rotation_matrix)

    def set_pose_from_frame(self, pose, frame, **kwargs):
        self._set_joint_from_frame_recurse(frame, pose.get_root_joint(), **kwargs)
        self.update_pose_world_positions(pose)

    def get_root_joint_definition(self):
        return self._root_joint_definition

    def get_joint_definition(self, name):
        return self._joint_definitions[name]

    def _set_joint_from_frame_recurse(self, frame, joint, frame_data_index=0, convert_to_z_up=False):
        joint_dict = dict()
        for channel in joint.definition.channels:
            joint_dict[channel] = frame[frame_data_index]
            frame_data_index += 1
            
        self._set_joint_from_dict(joint, joint_dict, convert_to_z_up)

        for child in joint.children:
            frame_data_index = self._set_joint_from_frame_recurse(
                frame, child, frame_data_index, convert_to_z_up)
            if(frame_data_index == 0):
                raise Exception("fatal error")

        return frame_data_index
            
    def _set_joint_from_dict(self, joint, joint_dict, convert_to_z_up=False):
        if "Xposition" in joint_dict:
            if convert_to_z_up:
                if "Yposition" in joint_dict and "Zposition" in joint_dict:
                    new_z = joint_dict["Yposition"]
                    new_y = -joint_dict["Zposition"]
                    joint_dict["Zposition"] = new_z
                    joint_dict["Yposition"] = new_y
                    
            joint.translation = array([
                    joint_dict["Xposition"],
                    joint_dict["Yposition"],
                    joint_dict["Zposition"]])

        if joint.definition.has_rotation:
            joint.angles = [math.radians(joint_dict[channel])
                            for channel in joint.definition.rotation_channels]
            if convert_to_z_up:
                rotation_matrix = euler_matrix(*joint.angles, axes=joint.definition.axes)
                rotation_matrix_z_up = self._convert_rotation_matrix_to_z_up(rotation_matrix)
                new_angles = list(euler_from_matrix(rotation_matrix_z_up, axes=joint.definition.axes))
                joint.angles = new_angles
            
            joint.rotation = Euler(joint.angles, joint.definition.axes)

    def _convert_rotation_matrix_to_z_up(self, m):
        r = numpy.array(m)

        r[0][1] = -m[0][2]
        r[0][2] =  m[0][1]

        r[1][0] = -m[2][0]
        r[1][1] =  m[2][2]
        r[1][2] = -m[2][1]

        r[2][0] =  m[1][0]
        r[2][1] = -m[1][2]
        r[2][2] =  m[1][1]
        
        return r
    
    def set_pose_from_joint_dicts(self, pose, joint_dicts):
        self._set_joint_from_dicts_recurse(pose.get_root_joint(), joint_dicts)
        self.update_pose_world_positions(pose)

    def _set_joint_from_dicts_recurse(self, joint, joint_dicts):
        try:
            self._set_joint_from_dict(joint, joint_dicts[joint.definition.index])
        except Exception as exception:
            raise Exception("Failed to set joint from dict for joint %r: %s" % (
                joint.definition.name, exception))
        for child in joint.children:
            self._set_joint_from_dicts_recurse(child, joint_dicts)

    def update_pose_world_positions(self, pose):
        self._update_world_position_recurse(pose.get_root_joint())

    def _update_world_position_recurse(self, joint):
        if joint.definition.has_parent:
            parent_trtr = joint.parent.trtr
            localtoworld = dot(parent_trtr, joint.definition.translation_matrix)
        else:
            translation_matrix = make_translation_matrix(*joint.translation)
            localtoworld = dot(joint.definition.translation_matrix, translation_matrix)

        if joint.definition.has_rotation:
            if joint.definition.has_static_rotation:
                rotation_matrix = self._static_rotation_matrix(joint)
            else:
                rotation_matrix = euler_matrix(*joint.angles, axes=joint.definition.axes)
            trtr = dot(localtoworld, rotation_matrix)
        else:
            trtr = localtoworld
        joint.trtr = trtr

        worldpos = array([
                  localtoworld[0,3],
                  localtoworld[1,3],
                  localtoworld[2,3],
                  localtoworld[3,3] ])
        joint.worldpos = worldpos

        for child in joint.children:
            self._update_world_position_recurse(child)

    def _static_rotation_matrix(self, joint):
        if not hasattr(joint, "static_rotation_matrix"):
            joint.definition.static_rotation_matrix = euler_matrix(
                *joint.definition.static_angles, axes=joint.definition.axes)
        return joint.definition.static_rotation_matrix

    def pretty_print(self):
        self._pretty_print_recurse(self._root_joint_definition)

    def _pretty_print_recurse(self, joint_definition, indent=0):
        print("%sname=%r channels=%r offset=%r" % (
            indent * "  ", joint_definition.name, joint_definition.channels, joint_definition.offset))
        for child_definition in joint_definition.child_definitions:
            self._pretty_print_recurse(child_definition, indent+1)

    def get_rotation_index(self, axis):
        return self._root_joint_definition.get_rotation_index(axis)

class HierarchyCreator:
    def create_hiearchy_from_dict(self, dict_):
        self._joint_index = 0
        root_node_definition = self._create_joint_definition_from_dict_recurse(dict_)
        return Hierarchy(root_node_definition)
    
    def _create_joint_definition_from_dict_recurse(self, dict_):
        is_root = (self._joint_index == 0)

        joint_definition = self._create_joint_definition(
            name=dict_["name"],
            root=is_root)

        if "children" in dict_:
            child_dicts = dict_["children"]
        else:
            child_dicts = []

        if len(child_dicts) == 0:
            end = self._create_joint_definition(
                name=dict_["name"] + "End",
                is_end=True)
            joint_definition.add_child_definition(end)
        else:
            for child_dict in child_dicts:
                child_definition = self._create_joint_definition_from_dict_recurse(child_dict)
                joint_definition.add_child_definition(child_definition)

        return joint_definition

    def _create_joint_definition(self, name=None, root=False, is_end=False):
        if root:
            channels = ["Xposition", "Yposition", "Zposition", "Xrotation", "Yrotation", "Zrotation"]
        elif is_end:
            channels = []
        else:
            channels = ["Xrotation", "Yrotation", "Zrotation"]
        joint_definition = JointDefinition(
            name, self._joint_index,
            channels=channels,
            is_end=is_end)
        self._joint_index += 1
        return joint_definition

class Pose:
    def __init__(self, hierarchy):
        self._hierarchy = hierarchy
        self._root_joint = hierarchy.get_root_joint_definition().create_joint()
        self._create_joints_dict()

    def _create_joints_dict(self):
        self._joints_by_name = dict()
        self._populate_joints_dict_recurse(self._root_joint)

    def _populate_joints_dict_recurse(self, joint):
        self._joints_by_name[joint.definition.name] = joint
        for child in joint.children:
            self._populate_joints_dict_recurse(child)

    def get_root_joint(self):
        return self._root_joint

    def get_vertices(self):
        return self._root_joint.get_vertices()

    def get_joint(self, name):
        return self._joints_by_name[name]

class ScaleInfo:
    min_x = None
    max_pose_size = 0

    def update_with_vector(self, x, y, z):
        if self.min_x is None:
            self.min_x = self.max_x = x
            self.min_y = self.max_y = y
            self.min_z = self.max_z = z
        else:
            self.min_x = min(self.min_x, x)
            self.min_y = min(self.min_y, y)
            self.min_z = min(self.min_z, z)
            self.max_x = max(self.max_x, x)
            self.max_y = max(self.max_y, y)
            self.max_z = max(self.max_z, z)

    def update_scale_factor(self):
        if self.max_pose_size == 0:
            print("Warning: max_pose_size==0. Setting scale_factor to 1.")
            self.scale_factor = 1
        else:
            self.scale_factor = self.max_pose_size

    def update_max_pose_size(self, vertices):
        for coordinate in range(3):
            values = [vertex[coordinate] for vertex in vertices]
            this_size = max(values) - min(values)
            self.max_pose_size = max(self.max_pose_size, this_size)
