import unittest
from mock import patch

import application

class CreateRecallTestCase(unittest.TestCase):
    def given_memory_has_num_frames(self, num_frames):
        self._memory = application.Memory()
        self._memory.set_frames([0] * num_frames)

    def when_create_random_recall(self, *args, **kwargs):
        self._memory.create_random_recall(*args, **kwargs)

    def then_rantint_invoked_with(self, *args):
        self._mock_random.randint.assert_called_once_with(*args)

    def setUp(self):
        self._patcher = patch("application.random")
        self._mock_random = self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        
    def test_num_frames_to_recall_equals_recency_num_frames_equals_memory_num_frames(self):
        self.given_memory_has_num_frames(8)
        self.when_create_random_recall(num_frames_to_recall=8, recency_num_frames=8)
        self.then_rantint_invoked_with(0, 0)
        
    def test_num_frames_to_recall_equals_recency_num_frames_less_than_memory_num_frames(self):
        self.given_memory_has_num_frames(8)
        self.when_create_random_recall(num_frames_to_recall=3, recency_num_frames=3)
        self.then_rantint_invoked_with(5, 5)

    def test_num_frames_to_recall_more_than_recency_num_frames_and_equals_memory_num_frames(self):
        self.given_memory_has_num_frames(8)
        self.when_create_random_recall(num_frames_to_recall=8, recency_num_frames=3)
        self.then_rantint_invoked_with(0, 0)

    def test_num_frames_to_recall_more_than_recency_num_frames_and_less_than_memory_num_frames_without_freedom(self):
        self.given_memory_has_num_frames(8)
        self.when_create_random_recall(num_frames_to_recall=6, recency_num_frames=3)
        self.then_rantint_invoked_with(2, 2)

    def test_num_frames_to_recall_more_than_recency_num_frames_and_less_than_memory_num_frames_with_freedom(self):
        self.given_memory_has_num_frames(8)
        self.when_create_random_recall(num_frames_to_recall=3, recency_num_frames=5)
        self.then_rantint_invoked_with(3, 5)
                
    def test_num_frames_to_recall_less_than_recency_num_frames_and_equals_memory_num_frames(self):
        self.given_memory_has_num_frames(8)
        self.when_create_random_recall(num_frames_to_recall=8, recency_num_frames=20)
        self.then_rantint_invoked_with(0, 0)
                
    def test_num_frames_to_recall_less_than_recency_num_frames_and_less_than_memory_num_frames(self):
        self.given_memory_has_num_frames(8)
        self.when_create_random_recall(num_frames_to_recall=3, recency_num_frames=20)
        self.then_rantint_invoked_with(0, 5)

    def test_recency_num_frames_none_and_num_frames_to_recall_less_then_memory_num_frames(self):
        self.given_memory_has_num_frames(8)
        self.when_create_random_recall(num_frames_to_recall=3, recency_num_frames=None)
        self.then_rantint_invoked_with(0, 5)
        
    def test_recency_num_frames_none_and_num_frames_to_recall_equals_memory_num_frames(self):
        self.given_memory_has_num_frames(8)
        self.when_create_random_recall(num_frames_to_recall=8, recency_num_frames=None)
        self.then_rantint_invoked_with(0, 0)

class GetFrameByIndexTestCase(unittest.TestCase):
    def given_memory_with_frames(self, frames):
        self._memory = application.Memory()
        self._memory.set_frames(frames)

    def when_get_frame_by_index(self, index):
        self._result = self._memory.get_frame_by_index(index)

    def then_result_is(self, expected_result):
        self.assertEquals(expected_result, self._result)
        
    def test_base_case(self):
        self.given_memory_with_frames(["a", "b", "c"])
        self.when_get_frame_by_index(1)
        self.then_result_is("b")
        
    def test_negative_index_returns_first_element(self):
        self.given_memory_with_frames(["a", "b", "c"])
        self.when_get_frame_by_index(-1)
        self.then_result_is("a")
        
    def test_too_high_index_returns_last_element(self):
        self.given_memory_with_frames(["a", "b", "c"])
        self.when_get_frame_by_index(3)
        self.then_result_is("c")
