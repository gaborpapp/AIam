#!/usr/bin/env python

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/../../bvh/bvhplay")

from svg_exporter import SvgExporter
from bvh.bvh_writer import BvhWriter
import os
import sklearn.neighbors
import numpy

class PoseMapContentsPlotter:
    _bvh_tempfile_path = "_temp.bvh"

    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("--output", "-o", default="pose_map.svg")
        parser.add_argument("--plot-size", type=float, default=500)
        parser.add_argument("--padding", type=float, default=5)
        parser.add_argument("--camera-x", "-cx", type=float, default=0)
        parser.add_argument("--camera-y", "-cy", type=float, default=10)
        parser.add_argument("--camera-z", "-cz", type=float, default=1500)
        parser.add_argument("--grid-resolution", type=int, default=10)
        parser.add_argument("--stroke-width", type=float, default=2.0)
        parser.add_argument("--reflect-observed-regions", action="store_true")
        parser.add_argument("--min-stroke-width", type=float, default=2.0)
        parser.add_argument("--stroke-width-contrast", type=float, default=.5)
        parser.add_argument("--min-opacity", type=float, default=.6)
        parser.add_argument("--opacity-contrast", type=float, default=1)
        parser.add_argument("--background-color")
        parser.add_argument("--animate-learning", action="store_true")
        parser.add_argument("--training-epochs-per-frame", type=int, default=1)
    
    def __init__(self, experiment, args):
        self._experiment = experiment
        self._args = args
        self._explored_range = 1.0 + experiment.args.explore_beyond_observations
        self._explored_min = .5 - self._explored_range/2
        self._explored_max = .5 + self._explored_range/2

    def plot(self):
        if self._experiment.student.num_reduced_dimensions > 2:
            print("WARNING: model has %d dimensions, but %s only considers the first 2" % \
                (self._experiment.student.num_reduced_dimensions, self.__class__.__name__))
        contrainers = self._experiment.entity._unnormalized_constrainers
        if contrainers.enable_friction or contrainers.enable_floor:
            print("WARNING: constrainers applied in entity, but this may not be handled properly by %s " \
                "since a single pose object is used throughout the grid" % self.__class__.__name__)

        if self._args.animate_learning:
            self._plot_learning_animation()
        else:
            self._experiment._load_model()
            self._plot_frame(self._args.output)

    def _plot_learning_animation(self):
        base_path = self._args.output[:-len(".svg")]
        i = 0
        while True:
            if i % self._args.training_epochs_per_frame == 0:
                frame_path = "%s.%08d.svg" % (base_path, i)
                self._experiment.student.probe(self._experiment._training_data)
                self._plot_frame(frame_path)
            self._experiment.student.train(self._experiment._training_data)
            i += 1

    def _plot_frame(self, path):
        if self._args.reflect_observed_regions:
            self._approximate_distances_to_nearest_observation()
        self._out = open(path, "w")
        self._outer_cell_size = self._args.plot_size / self._args.grid_resolution
        self._inner_cell_size = self._outer_cell_size - 2 * self._args.padding
        self._generate_header()
        for grid_y in range(self._args.grid_resolution):
            for grid_x in range(self._args.grid_resolution):
                self._render_cell(grid_x, grid_y)
        self._generate_footer()
        self._out.close()

    def _approximate_distances_to_nearest_observation(self):
        self._nearest_neighbor_classifier = sklearn.neighbors.KNeighborsClassifier(
            n_neighbors=1, weights='uniform')
        self._nearest_neighbor_classifier.fit(
            self._experiment.student.normalized_observed_reductions,
            self._experiment.student.normalized_observed_reductions)

        self._distances_to_nearest_observation = numpy.zeros(
            (self._args.grid_resolution, self._args.grid_resolution))

        for grid_y in range(self._args.grid_resolution):
            for grid_x in range(self._args.grid_resolution):
                normalized_reduction = self._get_normalized_reduction(grid_x, grid_y)
                self._distances_to_nearest_observation[grid_x, grid_y] = self._distance_to_nearest_observation(
                    normalized_reduction)

        self._distances_to_nearest_observation -= numpy.amin(self._distances_to_nearest_observation)
        self._distances_to_nearest_observation /= numpy.amax(self._distances_to_nearest_observation)

    def _distance_to_nearest_observation(self, normalized_reduction):
        nearest_observation = self._nearest_neighbor_classifier.predict(normalized_reduction)[0]
        return numpy.linalg.norm(normalized_reduction - nearest_observation)

    def _render_cell(self, grid_x, grid_y):
        normalized_reduction = self._get_normalized_reduction(grid_x, grid_y)

        px = float(grid_x) / self._args.grid_resolution * self._args.plot_size + self._args.padding
        py = float(grid_y) / self._args.grid_resolution * self._args.plot_size + self._args.padding

        if self._args.reflect_observed_regions:
            stroke_width = self._args.min_stroke_width + (
                (1 - pow(self._distances_to_nearest_observation[grid_x, grid_y],
                         self._args.stroke_width_contrast))
                * (self._args.stroke_width - self._args.min_stroke_width))

            opacity = self._args.min_opacity + (
                (1 - pow(self._distances_to_nearest_observation[grid_x, grid_y],
                         self._args.opacity_contrast))
                * (1 - self._args.min_opacity))
        else:
            stroke_width = self._args.stroke_width
            opacity = 1
            
        self._get_pose(normalized_reduction)
        self._render_pose(px, py, stroke_width, opacity)

    def _get_normalized_reduction(self, grid_x, grid_y):
        normalized_reduction = [0.5] * self._experiment.student.num_reduced_dimensions
        if self._args.grid_resolution > 1:
            normalized_reduction[0] = float(grid_x) / (self._args.grid_resolution - 1) \
                                      * self._explored_range + self._explored_min
            normalized_reduction[1] = float(grid_y) / (self._args.grid_resolution - 1) \
                                      * self._explored_range + self._explored_min
        return normalized_reduction
        
    def _get_pose(self, normalized_reduction):
        reduction = self._experiment.student.unnormalize_reduction(normalized_reduction)
        output = self._experiment.student.inverse_transform(numpy.array([reduction]))[0]
        self._experiment.entity.parameters_to_processed_pose(output, self._experiment.pose)

    def _render_pose(self, px, py, stroke_width, opacity):
        self._save_pose_as_temp_bvh()
        self._export_temp_bvh_to_svg(px, py, stroke_width, opacity)
        self._delete_temp_bvh()

    def _save_pose_as_temp_bvh(self):
        bvh_writer = BvhWriter(
            self._experiment.bvh_reader.get_hierarchy(),
            self._experiment.bvh_reader.get_frame_time())
        bvh_writer.add_pose_as_frame(self._experiment.pose)
        bvh_writer.write(self._bvh_tempfile_path)

    def _export_temp_bvh_to_svg(self, px, py, stroke_width, opacity):
        bvh_to_svg_exporter = SvgExporter(
            self._bvh_tempfile_path,
            self._args.camera_x, self._args.camera_y, self._args.camera_z)
        bvh_to_svg_exporter.export_frame(
            self._out,
            t=0,
            x=px,
            y=py,
            width=self._inner_cell_size,
            height=self._inner_cell_size,
            opacity=opacity,
            stroke_width=stroke_width,
            auto_crop=True)

    def _delete_temp_bvh(self):
        os.unlink(self._bvh_tempfile_path)
        
    def _generate_header(self):
        self._write('<svg xmlns="http://www.w3.org/2000/svg" version="1.1">\n')
        if self._args.background_color:
            self._write('<rect width="%f" height="%f" fill="%s" />' % (
                    self._args.plot_size, self._args.plot_size, self._args.background_color))
        self._write('<g>\n')

    def _generate_footer(self):
        self._write('</g>\n')
        self._write('</svg>\n')

    def _write(self, string):
        print(string, file=self._out)
