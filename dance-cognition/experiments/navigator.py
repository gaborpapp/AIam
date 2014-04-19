import sklearn.neighbors
import numpy
import copy
from scipy.interpolate import InterpolatedUnivariateSpline
import envelope as envelope_module
import random

class Navigator:
    def __init__(self, map_points):
        self.map_points = map_points
        self._n_dimensions = len(map_points[0])
        self._nearest_neighbor_classifier = sklearn.neighbors.KNeighborsClassifier(
            n_neighbors=1, weights='uniform')
        self._nearest_neighbor_classifier.fit(map_points, map_points)
        self._departure = None

    def random_point_in_map_space(self):
        return numpy.array([random.uniform(0., 1.)
                            for n in range(self._n_dimensions)])

    def generate_path(self, departure, num_segments, novelty, num_trials=10, resolution=100):
        self._departure = departure
        self._num_segments = num_segments
        self._novelty = novelty
        self._resolution = resolution
        return self._choose_best_random_path(num_trials)

    def _choose_best_random_path(self, num_trials):
        choices = [self._generate_path_to_random_destination()
                   for n in range(num_trials)]
        return min(
            choices,
            key=lambda path: self._score_path(path))

    def _generate_path_to_random_destination(self):
        self._destination = self.random_point_in_map_space()
        self._segments = [self._departure]
        for n in range(self._num_segments-1):
            self._add_path_segment(n)
        return self._interpolate_path(self._segments, self._resolution)

    def _score_path(self, path):
        novelty_score = self._score_novelty(path)
        distance_score = self._score_distance(path)
        return novelty_score * distance_score

    def _score_novelty(self, path):
        actual_novelty = self._estimate_novelty(path)
        return abs(actual_novelty - self._novelty)

    def _score_distance(self, path):
        if self._departure is None:
            return 1
        else:
            actual_distance = self._distance(path[-1], self._departure)
            desired_distance = .5 # TEMP
            return abs(actual_distance - desired_distance)

    def _estimate_novelty(self, path):
        return sum([self._distance_to_nearest_map_point(point)
                    for point in path]) / len(path)

    def _distance_to_nearest_map_point(self, point):
        nearest_map_point = self._nearest_neighbor_classifier.predict(point)[0]
        return self._distance(point, nearest_map_point)

    def _interpolate_path(self, uninterpolated_path, resolution):
        uninterpolated_path_numpy = numpy.array(uninterpolated_path)
        unclamped_interpolated_path = numpy.column_stack(
                [self._spline_interpolation_1d(uninterpolated_path_numpy[:,n], resolution)
                 for n in range(self._n_dimensions)])
        return list(self._clamp_path(unclamped_interpolated_path, uninterpolated_path))

    def _spline_interpolation_1d(self, points, resolution):
        x = numpy.arange(0., 1., 1./len(points))
        x_new = numpy.arange(0., 1., 1./resolution)
        curve = InterpolatedUnivariateSpline(x, points)
        return curve(x_new)

    def _clamp_path(self, unclamped_interpolated_path, uninterpolated_path):
        startpoint = uninterpolated_path[0]
        endpoint = uninterpolated_path[-1]
        index_nearest_start = self._nearest_index(unclamped_interpolated_path, startpoint)
        index_nearest_end = self._nearest_index(unclamped_interpolated_path, endpoint)
        return unclamped_interpolated_path[index_nearest_start:index_nearest_end]

    def _nearest_index(self, iterable, target):
        return min(range(len(iterable)),
                   key=lambda i: self._distance(iterable[i], target))

    def _distance(self, a, b):
        return numpy.linalg.norm(a - b)

    def _add_path_segment(self, n):
        previous_point = self._segments[-1]
        next_point_straightly = previous_point + (self._destination - previous_point) \
            / (self._num_segments - n - 1)
        next_point_in_map = self._nearest_neighbor_classifier.predict(
            next_point_straightly)[0]
        next_point = next_point_in_map + (next_point_straightly - next_point_in_map) * \
            min(1, self._novelty*0.3)
        if not numpy.array_equal(next_point, previous_point):
            self._segments.append(next_point)


class PathFollower:
    def __init__(self, path, velocity, envelope):
        self._path = path
        self._desired_average_velocity = velocity
        self._velocity_correction = 1.
        if envelope.__class__ != envelope_module.constant_envelope():
            self._velocity_correction = \
                self._estimate_duration(envelope_module.constant_envelope()) / \
                self._estimate_duration(envelope)
        self._velocity_envelope = envelope
        self._restart()

    def _restart(self):
        self._position = self._path[0]
        self._remaining_path = copy.copy(self._path)
        self._activate_next_path_strip()

    def _estimate_duration(self, velocity_envelope):
        self._velocity_envelope = velocity_envelope
        self._restart()
        duration = 0.
        while not self.reached_destination():
            duration += self.proceed()
        return duration

    def proceed(self, max_time_to_process=None):
        self._time_processed = 0.
        self._max_time_to_process = max_time_to_process
        while (self._max_time_to_process is None or self._max_time_to_process > 0) \
                and not self.reached_destination():
            self._process_within_state()
        return self._time_processed

    def current_position(self):
        return self._position

    def _process_within_state(self):
        if self._reached_path_strip_destination():
            self._remaining_path.pop(0)
            self._activate_next_path_strip()
        else:
            self._move_along_path_strip()

    def reached_destination(self):
        return len(self._remaining_path) <= 1

    def _reached_path_strip_destination(self):
        return self._travel_time_in_strip >= self._current_strip_duration

    def _activate_next_path_strip(self):
        if len(self._remaining_path) >= 2:
            self._current_strip_departure = self._remaining_path[0]
            self._current_strip_destination = self._remaining_path[1]
            self._current_strip_duration = self._current_strip_distance() / \
                self._current_strip_velocity()
            self._travel_time_in_strip = 0.0

    def _current_strip_distance(self):
        return numpy.linalg.norm(self._current_strip_destination - self._current_strip_departure)

    def _current_strip_velocity(self):
        return self._velocity_envelope.envelope((self._relative_cursor())) \
            * self._desired_average_velocity \
            / self._velocity_correction

    def _relative_cursor(self):
        return 1 - len(self._remaining_path) / float(len(self._path))

    def _move_along_path_strip(self):
        remaining_time_in_strip = self._current_strip_duration - self._travel_time_in_strip
        if self._max_time_to_process is None:
            duration_to_move = remaining_time_in_strip
        else:
            duration_to_move = min(self._max_time_to_process, remaining_time_in_strip)
        self._position = self._current_strip_departure + \
            (self._current_strip_destination - self._current_strip_departure) * \
            self._travel_time_in_strip / (self._current_strip_duration)
        self._travel_time_in_strip += duration_to_move
        self._time_processed += duration_to_move
        if self._max_time_to_process is not None:
            self._max_time_to_process -= duration_to_move
