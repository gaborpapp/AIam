import sklearn.neighbors
import numpy
import copy
import dynamics as dynamics_module
import random
import math

NUM_DESTINATION_CANDIDATES = 50

class Navigator:
    def __init__(self, map_points):
        self._nearest_neighbor_regressor = sklearn.neighbors.KNeighborsRegressor(
            n_neighbors=1, weights='uniform')
        self.set_map_points(map_points)
        self._n_dimensions = len(map_points[0])
        self._max_distance = math.sqrt(self._n_dimensions) / 2
        self._departure = None
        self._preferred_location = None

    def set_map_points(self, map_points):
        self.map_points = map_points
        self._nearest_neighbor_regressor.fit(map_points, map_points)
        
    def set_preferred_location(self, location):
        self._preferred_location = location

    def get_preferred_location(self):
        return self._preferred_location

    def _select_destination(self, novelty=.0):
        if self._departure is None:
            return self._generate_destination(novelty)
        else:
            return self._select_best_destination(novelty)

    def _select_best_destination(self, novelty):
        destination_candidates = [
            self._generate_destination(novelty)
            for n in range(NUM_DESTINATION_CANDIDATES)]
        best_destination = min(
            destination_candidates,
            key=lambda destination: self._score_destination(destination))
        return best_destination

    def _generate_destination(self, novelty):
        known_destination = random.choice(self.map_points)
        return known_destination + self._random_vector_of_magnitude(novelty)

    def _score_destination(self, destination):
        score = self._difference_from_extension(destination)
        if self._preferred_location is not None:
            score += self._location_preference * self._distance_from_preferred_location(destination)
        return score

    def _difference_from_extension(self, destination):
        distance = self._distance(self._departure, destination)
        return abs(distance - self._extension)

    def _distance_from_preferred_location(self, destination):
        return self._distance(destination, self._preferred_location)

    def _random_vector_of_magnitude(self, magnitude):
        v = self._random_vector()
        return v / numpy.linalg.norm(v) * magnitude

    def _random_vector(self):
        return numpy.array([random.uniform(-1, 1) for n in range(self._n_dimensions)])

    def generate_path(self, departure, num_segments, novelty, extension, location_preference):
        self._departure = departure
        self._num_segments = num_segments
        self._extension = self._max_distance * extension
        self._location_preference = location_preference
        self._destination = self._select_destination(novelty)
        self._segments = [departure]
        for n in range(num_segments-1):
            self._add_path_segment(n, novelty)
        return self._segments

    def _distance(self, a, b):
        return numpy.linalg.norm(a - b)

    def _add_path_segment(self, n, novelty):
        previous_point = self._segments[-1]
        next_point_straightly = previous_point + (self._destination - previous_point) \
            / (self._num_segments - n - 1)
        next_point_in_map = self._nearest_neighbor_regressor.predict(
            [next_point_straightly])[0][0]
        next_point = next_point_in_map + (next_point_straightly - next_point_in_map) * \
            min(1, novelty*0.3)
        if not numpy.array_equal(next_point, previous_point):
            self._segments.append(next_point)


class PathFollower:
    def __init__(self, path, dynamics):
        self._path = path
        self._velocity_correction = 1.
        if dynamics.__class__ != dynamics_module.constant_dynamics():
            estimated_duration = self._estimate_duration(dynamics)
            if estimated_duration > 0:
                self._velocity_correction = self._estimate_duration(dynamics_module.constant_dynamics()) / \
                                            self._estimate_duration(dynamics)
        self._dynamics = dynamics
        self._restart()

    def _restart(self):
        self._position = self._path[0]
        self._remaining_path = copy.copy(self._path)
        self._activate_next_path_strip()

    def _estimate_duration(self, dynamics):
        self._dynamics = dynamics
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
        return self._dynamics.velocity((self._relative_cursor())) \
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
