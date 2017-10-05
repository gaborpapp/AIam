import bvh_reader
from numpy import array
import copy

class BvhCollection:
    def __init__(self, filenames):
        readers = [bvh_reader.BvhReader(filename) for filename in filenames]
        self._init_readers(readers)

    def _init_readers(self, readers):
        self._readers = readers
        self._base_reader = self._readers[0]

    def get_readers(self):
        return self._readers

    def read(self, read_frames=True):
        self._read_bvhs(read_frames)
        self._set_scale_info()
        self._hierarchy = self._create_hierachy()

    def _read_bvhs(self, read_frames):
        self._duration = 0
        self._num_frames = 0
        index = 0
        for reader in self._readers:
            reader.read(read_frames)
            reader.index = index
            reader.start_time = self._duration
            reader.end_time = self._duration + reader.get_duration()
            reader.start_index = self._num_frames
            reader.end_index = self._num_frames + reader.get_num_frames()
            self._duration += reader.get_duration()
            self._num_frames += reader.get_num_frames()
            index += 1

    def _set_scale_info(self):
        self._scale_info = bvh_reader.ScaleInfo()
        for reader in self._readers:
            self._scale_info.update_with_vector(
                reader._scale_info.min_x,
                reader._scale_info.min_y,
                reader._scale_info.min_z)
            self._scale_info.update_with_vector(
                reader._scale_info.max_x,
                reader._scale_info.max_y,
                reader._scale_info.max_z)
            self._scale_info.max_pose_size = max(
                self._scale_info.max_pose_size,
                reader._scale_info.max_pose_size)
        self._scale_info.update_scale_factor()

    def _create_hierachy(self):
        hierarchy = copy.deepcopy(self._base_reader.get_hierarchy())
        self._set_static_orientation_recurse(hierarchy.get_root_joint_definition())
        return hierarchy

    def _set_static_orientation_recurse(self, joint_definition):
        self._set_static_orientation(joint_definition)
        for child_definition in joint_definition.child_definitions:
            self._set_static_orientation_recurse(child_definition)

    def _set_static_orientation(self, joint_definition):
        joint_definition.has_static_rotation = all([
                reader.get_hierarchy().get_joint_definition(joint_definition.name).has_static_rotation
                for reader in self._readers])

    def get_frame_time(self):
        return self._base_reader.get_frame_time()

    def set_pose_from_frame(self, pose, frame):
        return self._base_reader.set_pose_from_frame(pose, frame)

    def set_pose_from_frame_index(self, pose, frame_index):
        return self._base_reader.set_pose_from_frame_index(pose, frame_index)

    def get_duration(self):
        return self._duration

    def set_pose_from_time(self, pose, t):
        reader = self.get_reader_at_time(t)
        reader.set_pose_from_time(pose, t - reader.start_time)

    def get_reader_at_time(self, t):
        for reader in self._readers:
            if reader.start_time <= t and t < reader.end_time:
                return reader
        return self._readers[-1]

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
        return self._hierarchy

    def vertices_to_edges(self, *args, **kwargs):
        return self._base_reader.vertices_to_edges(*args, **kwargs)

    def get_num_joints(self):
        return self._hierarchy.get_num_joints()

    def get_num_frames(self):
        return self._num_frames

    def get_frame_by_index(self, index):
        for reader in self._readers:
            if reader.start_index <= index < reader.end_index:
                return reader.get_frame_by_index(index - reader.start_index)
