import unittest
import transformations
import numpy
import math

class TransformationsTestCase(unittest.TestCase):
    def test_euler_from_matrix_specific_case(self):
        R0 = transformations.euler_matrix(1, 2, 3, 'syxz')
        al, be, ga = transformations.euler_from_matrix(R0, 'syxz')
        R1 = transformations.euler_matrix(al, be, ga, 'syxz')
        self.assertTrue(numpy.allclose(R0, R1), "Expected:\n%s\nbut got:\n%s" % (R1, R0))

    def test_euler_from_matrix_random_angles_all_axes(self):
        angles = (4*math.pi) * (numpy.random.random(3) - 0.5)
        successes = []
        failures = []
        for axes in list(transformations._AXES2TUPLE.keys()):
            R0 = transformations.euler_matrix(axes=axes, *angles)
            R1 = transformations.euler_matrix(axes=axes, *transformations.euler_from_matrix(R0, axes))
            if numpy.allclose(R0, R1):
                successes.append(axes)
            else:
                failures.append(axes)
        self.assertEqual(0, len(failures), "Failed for:\n%sand succeeded for:\n%s" % (failures, successes))
