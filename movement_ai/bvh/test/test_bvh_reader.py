import unittest
import copy
from bvh.bvh import JointDefinition

class JointDefinitionTestCase(unittest.TestCase):
    def test_deepcopy(self):
        self._given_a_joint_definition_with_children()
        self._when_deepcopy()
        self._then_result_contains_new_instances_with_maintained_hierarchy()

    def _given_a_joint_definition_with_children(self):
        self._source_hip = JointDefinition("Hip", 0, is_end=False)
        self._source_l_arm = JointDefinition("LArm", 1, is_end=True)
        self._source_r_arm = JointDefinition("RArm", 2, is_end=True)
        self._source_hip.child_definitions = [self._source_l_arm, self._source_r_arm]

    def _when_deepcopy(self):
        self._result_hip = copy.deepcopy(self._source_hip)

    def _then_result_contains_new_instances_with_maintained_hierarchy(self):
        self._assert_same_content_but_other_instance_recurse(self._result_hip, self._source_hip)

    def _assert_same_content_but_other_instance_recurse(self, joint_definition1, joint_definition2):
        self.assertFalse(joint_definition1 is joint_definition2)
        self.assertEqual(joint_definition1.name, joint_definition2.name)
        for child_definition1, child_definition2 in zip(joint_definition1.child_definitions,
                                                        joint_definition2.child_definitions):
            self._assert_same_content_but_other_instance_recurse(
                child_definition1, child_definition2)
