#!/usr/bin/env python

from PIL import Image
import numpy

class ModelPlotter:
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("--output", "-o", default="model.png")
        parser.add_argument("--plot-size", type=int, default=500)
        parser.add_argument("--plot-dimensions", help="e.g. 0,3 (x as 1st dimension and y as 4th)")
        parser.add_argument("--novelty", type=float, default=0)
        parser.add_argument("--radial-resolution", type=int, default=100)
        
    def __init__(self, experiment, args):
        self._experiment = experiment
        self._args = args
        self._size = self._args.plot_size
        if self._args.plot_dimensions:
            self._dimensions = [int(string) for string in self._args.plot_dimensions.split(",")]
        else:
            self._dimensions = [0, 1]

        self._explored_range = 1.0 + experiment.args.explore_beyond_observations
        self._explored_min = .5 - self._explored_range/2
        self._explored_max = .5 + self._explored_range/2

    def plot(self):
        self._create_observation_region_template()
        self._create_empty_buffer()
        self._add_observation_regions_to_buffer()
        self._convert_buffer_to_bitmap()
        self._save_bitmap_to_file()

    def _create_observation_region_template(self):
        radius = int(self._args.novelty * self._size)
        self._observation_region_size = radius * 2 + 1
        self._observation_region_template = numpy.zeros((
                self._observation_region_size,
                self._observation_region_size))
        for dx in range(-radius, radius+1):
            for dy in range(-radius, radius+1):
                if (dx*dx + dy*dy) <= radius*radius:
                    self._observation_region_template[dx + radius, dy + radius] = 1
        self._observation_region_radius = radius

    def _create_empty_buffer(self):
        self._output_buffer = numpy.zeros((self._size, self._size))

    def _add_observation_regions_to_buffer(self):
        print("creating plot...")
        for observation in self._experiment.student.normalized_observed_reductions:
            self._add_observation_region_to_buffer(observation)

    def _convert_buffer_to_bitmap(self):
        print("converting plot to bitmap...")
        monochromatic_bitmap = self._output_buffer.flatten('F')
        monochromatic_normalized_bitmap = monochromatic_bitmap / max(monochromatic_bitmap)
        rgb_normalized_bitmap = numpy.concatenate([[1-value]*3 for value in monochromatic_normalized_bitmap])
        self._rgb_bitmap = [int(value * 255) for value in rgb_normalized_bitmap]

    def _save_bitmap_to_file(self):
        print("saving bitmap...")
        image = Image.frombytes("RGB", (self._size, self._size),
                                data=self._array_to_string(self._rgb_bitmap))
        image.save(self._args.output)

    def _add_observation_region_to_buffer(self, observation):
        observation_px = self._normalized_reduction_value_to_bitmap_coordinate(observation[0])
        observation_py = self._normalized_reduction_value_to_bitmap_coordinate(observation[1])
        px1 = observation_px - self._observation_region_radius
        px2 = observation_px + self._observation_region_radius + 1
        py1 = observation_py - self._observation_region_radius
        py2 = observation_py + self._observation_region_radius + 1
        px1a = self._fit_within_boundaries(px1)
        px2a = self._fit_within_boundaries(px2)
        py1a = self._fit_within_boundaries(py1)
        py2a = self._fit_within_boundaries(py2)
        rx1 = px1a - px1
        rx2 = rx1 + (px2a - px1a)
        ry1 = py1a - py1
        ry2 = ry1 + (py2a - py1a)
        self._output_buffer[px1a:px2a, py1a:py2a] += self._observation_region_template[
            rx1:rx2, ry1:ry2]

    def _normalized_reduction_value_to_bitmap_coordinate(self, reduction_value):
        return int((reduction_value - self._explored_min) / self._explored_range * self._size)

    def _increase_pixel_value(self, px, py):
        self._output_buffer[px, py] += 1

    def _fit_within_boundaries(self, x):
        return min(max(x, 0), self._size)

    def _array_to_string(self, xs):
        return "".join([chr(int(x)) for x in xs])
