from angle_parameters import *
import unittest
import math
from transformations import euler_matrix, is_same_transform

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")
from bvh.geo import Euler

class AngleParametersTest(unittest.TestCase):
    def test_radians_vector2d_inversion(self):
        for n in range(100):
            r = float(n) / 100 * (math.pi*2)
            self._assert_radians_equal(r, vector2d_to_radians(radians_to_vector2d(r)))

    def _assert_radians_equal(self, x, y):
        self.assertAlmostEqual(
            self._clamp_radians(x),
            self._clamp_radians(y))

    def _clamp_radians(self, r):
        while r < 0:
            r += math.pi*2
        while r > math.pi*2:
            r -= math.pi*2
        return r

    def test_euler_to_3vectors_inversion(self):
        self._test_angle_3dof_inversion(EulerTo3Vectors)

    def test_euler_to_quaternion_inversion(self):
        self._test_angle_3dof_inversion(EulerToQuaternion)

    def test_euler_to_expmap_inversion(self):
        self._test_angle_3dof_inversion(EulerToExpmap)

    def _test_angle_3dof_inversion(self, parameterization):
        for axes in ["sxyz", "szyx"]:
            self._test_angle_3dof_inversion_for_axes(parameterization, axes)

    def _test_angle_3dof_inversion_for_axes(self, parameterization, axes):
        for n in range(100):
            t = float(n) / 100 * 2*math.pi * 4
            x = (t / 1) % (2*math.pi)
            y = (t / 2) % (2*math.pi)
            z = (t / 4) % (2*math.pi)

            euler = Euler((x, y, z), axes)
            parameters = parameterization.rotation_to_parameters(euler)
            self._assert_euler_equals(
                euler.angles,
                parameterization.parameters_to_rotation(parameters, euler.axes))

    def _assert_euler_equals(self, angles1, angles2):
        matrix1 = euler_matrix(*angles1)
        matrix2 = euler_matrix(*angles2)
        self.assertTrue(is_same_transform(matrix1, matrix2))
