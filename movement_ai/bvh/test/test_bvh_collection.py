import unittest
from bvh.bvh_collection import BvhCollection

class MockScaleInfo:
    min_x = 0
    min_y = 0
    min_z = 0
    max_x = 0
    max_y = 0
    max_z = 0
    max_pose_size = 0

class MockJointDefinition:
    def __init__(self, name, joints_with_static_rotation):
        self.name = name
        self.has_static_rotation = (self.name in joints_with_static_rotation)
        self.child_definitions = []

class MockHierarchy:
    def __init__(self, joints_with_static_rotation):
        self._joint_definitions = {}
        self._joints_with_static_rotation = joints_with_static_rotation
        self._add_joint_definition("Hip")
        self._add_joint_definition("LArm")
        self._add_joint_definition("RArm")
        self._root_joint_definition = self.get_joint_definition("Hip")
        self._root_joint_definition.child_definitions = [
            self.get_joint_definition("LArm"),
            self.get_joint_definition("RArm"),
            ]

    def _add_joint_definition(self, name):
        self._joint_definitions[name] = MockJointDefinition(name, self._joints_with_static_rotation)

    def get_root_joint_definition(self):
        return self._root_joint_definition

    def get_joint_definition(self, name):
        return self._joint_definitions[name]

class MockBvhReader:
    def __init__(self, duration=1.0, frames=None, num_frames=None, joints_with_static_rotation=[], frame_time=50):
        self._duration = duration
        if frames is None and num_frames is None:
            self._frames = ["mock_frame"]
            self._num_frames = 1
        else:
            self._frames = frames or ["mock_frame"] * num_frames
            self._num_frames = num_frames or len(self._frames)
        self._scale_info = MockScaleInfo()
        self._hierarchy = MockHierarchy(joints_with_static_rotation)
        self._frame_time = frame_time

    def read(self, read_frames):
        pass

    def get_duration(self):
        return self._duration

    def get_num_frames(self):
        return self._num_frames

    def get_hierarchy(self):
        return self._hierarchy

    def get_frame_time(self):
        return self._frame_time

    def get_frame_by_index(self, index):
        return self._frames[index]

class TestedBvhCollection(BvhCollection):
    def __init__(self, bvh_readers):
        self._init_readers(bvh_readers)

class BvhCollectionTestCase(unittest.TestCase):
    def test_duration_is_sum(self):
        self._given_bvh_reader(duration=10)
        self._given_bvh_reader(duration=5)
        self._given_created_bvh_collection()
        self._when_get_duration()
        self._then_result_is(15)

    def setUp(self):
        self._bvh_readers = []

    def _given_bvh_reader(self, **kwargs):
        self._bvh_readers.append(MockBvhReader(**kwargs))

    def _given_created_bvh_collection(self):
        self._bvh_collection = TestedBvhCollection(self._bvh_readers)
        self._bvh_collection.read()

    def _when_get_duration(self):
        self._result = self._bvh_collection.get_duration()

    def _then_result_is(self, expected_value):
        self.assertEqual(expected_value, self._result)

    def test_static_rotation_is_intersection(self):
        self._given_bvh_reader(joints_with_static_rotation=["LArm", "RArm", "Hip"])
        self._given_bvh_reader(joints_with_static_rotation=["LArm", "RArm"])
        self._given_bvh_reader(joints_with_static_rotation=["LArm"])
        self._given_created_bvh_collection()
        self._when_get_joints_with_static_rotation()
        self._then_result_items_are(["LArm"])

    def _when_get_joints_with_static_rotation(self):
        hierarchy = self._bvh_collection.get_hierarchy()
        self._result = self._get_joints_with_static_rotation(
            hierarchy.get_root_joint_definition())

    def _get_joints_with_static_rotation(self, joint_definition):
        result = set()
        if joint_definition.has_static_rotation:
            result.add(joint_definition.name)
        for child_definition in joint_definition.child_definitions:
            child_result = self._get_joints_with_static_rotation(child_definition)
            result = result.union(child_result)
        return result

    def _then_result_items_are(self, expected_value):
        self.assertItemsEqual(expected_value, self._result)

    def test_frame_time(self):
        self._given_bvh_reader(frame_time=100)
        self._given_created_bvh_collection()
        self._when_get_frame_time()
        self._then_result_is(100)

    def _when_get_frame_time(self):
        self._result = self._bvh_collection.get_frame_time()

    def test_get_num_frames_returns_sum(self):
        self._given_bvh_reader(num_frames=10)
        self._given_bvh_reader(num_frames=5)
        self._given_created_bvh_collection()
        self._when_get_num_frames()
        self._then_result_is(15)

    def _when_get_num_frames(self):
        self._result = self._bvh_collection.get_num_frames()
        
    def test_get_frame_by_index_for_last_reader(self):
        self._given_bvh_reader(frames=["mock_frame_0", "mock_frame_1"])
        self._given_bvh_reader(frames=["mock_frame_2"])
        self._given_created_bvh_collection()
        self._when_get_frame_by_index(2)
        self._then_result_is("mock_frame_2")
        
    def _when_get_frame_by_index(self, index):
        self._result = self._bvh_collection.get_frame_by_index(index)
        
    def test_get_frame_by_index_for_non_last_reader(self):
        self._given_bvh_reader(frames=["mock_frame_0", "mock_frame_1"])
        self._given_bvh_reader(frames=["mock_frame_2", "mock_frame_3"])
        self._given_bvh_reader(frames=["mock_frame_4"])
        self._given_created_bvh_collection()
        self._when_get_frame_by_index(2)
        self._then_result_is("mock_frame_2")
