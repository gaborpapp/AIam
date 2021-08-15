from scipy.interpolate import InterpolatedUnivariateSpline
import numpy

class InterpolationException(Exception): pass

def interpolate(uninterpolated_path, resolution):
    uninterpolated_path_numpy = numpy.array(uninterpolated_path)
    n_dimensions = len(uninterpolated_path[0])
    unclamped_interpolated_path = numpy.column_stack(
        [_spline_interpolation_1d(uninterpolated_path_numpy[:,n], resolution)
         for n in range(n_dimensions)])
    return list(_clamp_path(unclamped_interpolated_path, uninterpolated_path))

def _spline_interpolation_1d(points, resolution):
    x = numpy.arange(0., 1., 1./len(points))
    x_new = numpy.arange(0., 1., 1./resolution)
    k = min(3, len(points)-1)
    try:
        curve = InterpolatedUnivariateSpline(x, points, k=k)
    except Exception as exception:
        raise InterpolationException(exception)
    return curve(x_new)

def _clamp_path(unclamped_interpolated_path, uninterpolated_path):
    startpoint = uninterpolated_path[0]
    endpoint = uninterpolated_path[-1]
    index_nearest_start = _nearest_index(unclamped_interpolated_path, startpoint)
    index_nearest_end = _nearest_index(unclamped_interpolated_path, endpoint)
    return unclamped_interpolated_path[index_nearest_start:index_nearest_end]

def _nearest_index(iterable, target):
    return min(list(range(len(iterable))),
               key=lambda i: _distance(iterable[i], target))

def _distance(a, b):
    return numpy.linalg.norm(a - b)

def linear_interpolation(a, b, interpolation):
    return a + (b - a) * interpolation
