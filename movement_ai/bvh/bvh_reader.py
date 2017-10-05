# adopted from BVHplay (http://sourceforge.net/projects/bvhplay/)

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/../libs")

import cgkit.bvh
import os
import cPickle
from collections import defaultdict
from bvh import Hierarchy, ScaleInfo, JointDefinition
from geo import make_translation_matrix
from numpy import array

CHANNEL_TO_AXIS = {
    "Xrotation": "x",
    "Yrotation": "y",
    "Zrotation": "z",
}

class BvhReader(cgkit.bvh.BVHReader):
    def read(self, read_frames=True):
        if self._cache_exists():
            self._read(read_frames)
            self._load_from_cache()
        else:
            self._read(read_frames)
            self._probe_static_rotations()
            self._probe_vertex_range()
            self._save_to_cache()
        self._set_static_rotations()

    def _cache_exists(self):
        return os.path.exists(self._cache_filename())

    def _load_from_cache(self):
        cache_filename = self._cache_filename()
        # print "loading BVH cache from %s ..." % cache_filename
        f = open(cache_filename)
        self._scale_info = ScaleInfo()
        self._scale_info.__dict__ = cPickle.load(f)
        self._unique_rotations = cPickle.load(f)
        f.close()
        # print "ok"

    def _save_to_cache(self):
        cache_filename = self._cache_filename()
        # print "saving BVH cache to %s ..." % cache_filename
        f = open(cache_filename, "w")
        cPickle.dump(self._scale_info.__dict__, f)
        cPickle.dump(self._unique_rotations, f)
        f.close()
        # print "ok"

    def _cache_filename(self):
        return "%s.cache" % self.filename

    def _read(self, read_frames):
        cgkit.bvh.BVHReader.read(self, read_frames)
        self.hierarchy = self._create_hierarchy()
        self._num_joints = self.hierarchy.get_num_joints()
        self._duration = self._num_frames * self._frame_time

    def _create_hierarchy(self):
        self._joint_index = 0
        root_node_definition = self._process_node(self._root_node)
        return Hierarchy(root_node_definition)

    def _process_node(self, node, parentname='root'):
        name = node.name
        if (name == "End Site") or (name == "end site"):
            is_end = True
            name = parentname + "End"
        else:
            is_end = False
        joint_definition = JointDefinition(
            name=name, index=self._joint_index, is_end=is_end)
        self._joint_index += 1
        joint_definition.channels = node.channels

        joint_definition.offset = node.offset
        joint_definition.translation_matrix = make_translation_matrix(
            node.offset[0],
            node.offset[1],
            node.offset[2])

        if "Xrotation" in node.channels:
            joint_definition.rotation_channels = filter(
                lambda channel: channel in ["Xrotation", "Yrotation", "Zrotation"],
                node.channels)
            joint_definition.axes = "r" + "".join([
                    CHANNEL_TO_AXIS[channel] for channel in joint_definition.rotation_channels])
            joint_definition.rotation_index = self._create_rotation_index(joint_definition.rotation_channels)
            joint_definition.has_rotation = True
        else:
            joint_definition.has_rotation = False

        for child_node in node.children:
            child_definition = self._process_node(child_node, name)
            joint_definition.add_child_definition(child_definition)

        return joint_definition

    def _create_rotation_index(self, rotation_channels):
        result = {}
        for index, rotation_channel in enumerate(rotation_channels):
            result[rotation_channel] = index
        return result
    
    def get_duration(self):
        return self._duration

    def get_frame_time(self):
        return self._frame_time

    def get_num_frames(self):
        return self._num_frames

    def set_pose_from_time(self, pose, t):
        frame_index = self._frame_index(t)
        return self.set_pose_from_frame(pose, frame_index)

    def set_pose_from_frame_index(self, pose, frame_index):
        return self.set_pose_from_frame(pose, self.frames[frame_index])

    def set_pose_from_frame(self, pose, frame, **kwargs):
        return self.hierarchy.set_pose_from_frame(pose, frame, **kwargs)

    def normalize_vector(self, v):
        return self.normalize_vector_without_translation(
            array([v[0] - self._scale_info.min_x,
                   v[1] - self._scale_info.min_y,
                   v[2] - self._scale_info.min_z]))

    def normalize_vector_without_translation(self, v):
        return array([
            v[0] / self._scale_info.scale_factor * 2 - 1,
            v[1] / self._scale_info.scale_factor * 2 - 1,
            v[2] / self._scale_info.scale_factor * 2 - 1])

    def skeleton_scale_vector(self, v):
        return array([
            (v[0] + 1) / 2 * self._scale_info.scale_factor + self._scale_info.min_x,
            (v[1] + 1) / 2 * self._scale_info.scale_factor + self._scale_info.min_y,
            (v[2] + 1) / 2 * self._scale_info.scale_factor + self._scale_info.min_z])

    def get_hierarchy(self):
        return self.hierarchy

    def get_frame_by_index(self, frame_index):
        return self.frames[frame_index]

    def create_pose(self):
        return self.hierarchy.create_pose()

    def _frame_index(self, t):
        return int(t / self._frame_time) % self._num_frames

    def vertices_to_edges(self, vertices):
        edges = []
        self.hierarchy.get_root_joint_definition().populate_edges_from_vertices_recurse(
            vertices, edges)
        return edges

    def onHierarchy(self, root_node):
        self._root_node = root_node
        self.frames = []

    def onMotion(self, num_frames, frame_time):
        self._num_frames = num_frames
        self._frame_time = frame_time

    def onFrame(self, values):
        self.frames.append(values)

    def _probe_vertex_range(self):
        print "probing BVH vertex range..."
        self._scale_info = ScaleInfo()
        pose = self.hierarchy.create_pose()
        for n in range(self._num_frames):
            self.hierarchy.set_pose_from_frame(pose, self.frames[n])
            vertices = pose.get_vertices()
            for vertex in vertices:
                self._scale_info.update_with_vector(*vertex[0:3])
            self._scale_info.update_max_pose_size(vertices)
        self._scale_info.update_scale_factor()
        print "ok"

    def _probe_static_rotations(self):
        self._unique_rotations = defaultdict(set)
        if self._num_frames > 1:
            print "probing static rotations..."
            pose = self.hierarchy.create_pose()
            for n in range(self._num_frames):
                self.hierarchy.set_pose_from_frame(pose, self.frames[n])
                root_joint = pose.get_root_joint()
                self._process_static_rotations_recurse(root_joint)
            print "ok"

    def _process_static_rotations_recurse(self, joint):
        if joint.definition.has_rotation:
            self._update_rotations(joint)
        for child in joint.children:
            self._process_static_rotations_recurse(child)

    def _update_rotations(self, joint):
        previous_unique_rotations = self._unique_rotations[joint.definition.name]
        if len(previous_unique_rotations) < 2:
            self._unique_rotations[joint.definition.name].add(tuple(joint.angles))

    def _set_static_rotations(self):
        if self._num_frames > 1:
            for name, unique_rotations in self._unique_rotations.iteritems():
                if len(unique_rotations) == 1:
                    joint_definition = self.hierarchy.get_joint_definition(name)
                    joint_definition.has_static_rotation = True
                    joint_definition.static_angles = list(unique_rotations)[0]
