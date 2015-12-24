# adopted from BVHplay (http://sourceforge.net/projects/bvhplay/)

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/../libs")

import cgkit.bvh
import os
import cPickle
from collections import defaultdict
from bvh import Hierarchy, ScaleInfo

class BvhReader(cgkit.bvh.BVHReader):
    def read(self):
        if self._cache_exists():
            self._read()
            self._load_from_cache()
        else:
            self._read()
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

    def _read(self):
        cgkit.bvh.BVHReader.read(self)
        self.hierarchy = Hierarchy(self._root_nood, self.frames[0])
        self.num_joints = self.hierarchy.num_joints
        self._duration = self._num_frames * self._frame_time

    def get_duration(self):
        return self._duration

    def get_frame_time(self):
        return self._frame_time

    def get_num_frames(self):
        return self._num_frames

    def set_pose_from_time(self, pose, t):
        frame_index = self._frame_index(t)
        return self.hierarchy.set_pose_from_frame(pose, self.frames[frame_index])

    def get_hierarchy(self):
        return self.hierarchy

    def create_pose(self):
        return self.hierarchy.create_pose()

    def _frame_index(self, t):
        return int(t / self._frame_time) % self._num_frames

    def vertices_to_edges(self, vertices):
        edges = []
        self.hierarchy.get_root_joint_definition().populate_edges_from_vertices_recurse(
            vertices, edges)
        return edges

    def onHierarchy(self, root_nood):
        self._root_nood = root_nood
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
        self._scale_info.update_scale_factor()
        print "ok"

    def _probe_static_rotations(self):
        print "probing static rotations..."
        self._unique_rotations = defaultdict(set)
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
        for name, joints in self._unique_rotations.iteritems():
            if len(joints) == 1:
                joint_definition = self.hierarchy.get_joint_definition(name)
                joint_definition.has_static_rotation = True
