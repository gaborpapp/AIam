#!/usr/bin/env python

# gnuplot example for 3 components:
# set palette gray
# splot "observations.dat" with points pointsize 0.4 pointtype 7 palette

# export to EPS:
# set terminal postscript eps color
# set out "observations.eps"
# replot

from dimensionality_reduction.dimensionality_reduction_experiment import *
import re
import interpolation

parser = ArgumentParser()
parser.add_argument("--output", "-o")
parser.add_argument("--split-sensitivity", type=float)
parser.add_argument("--segments-output")
parser.add_argument("--plot-type", choices=["gnuplot", "svg"], default="gnuplot")
parser.add_argument("--stroke-width", type=float, default=1)
parser.add_argument("--stroke-width-min", type=float, default=1)
parser.add_argument("--stroke-opacity", type=float, default=.1)
parser.add_argument("--stroke-color", default="black")
parser.add_argument("--stroke-dasharray")
parser.add_argument("--plot-width", type=float, default=500)
parser.add_argument("--plot-height", type=float, default=500)
parser.add_argument("--point-size", type=float)
parser.add_argument("--point-size-min", type=float, default=1.5)
parser.add_argument("--plot-dimensions", help="e.g. 0,3 (x as 1st dimension and y as 4th)")
parser.add_argument("--select-bvh")
parser.add_argument("--interpolate", action="store_true")
parser.add_argument("--interpolation-resolution", type=int, default=100)
parser.add_argument("--observations-from-file")
parser.add_argument("--plot-joint-worldpos")
parser.add_argument("--background-color")

class ObservationsPlotter:
    def __init__(self, experiment):
        self._experiment = experiment
        self._args = experiment.args

    def plot(self):
        generator_class = eval("%sGenerator" % self._args.plot_type)

        if self._args.output:
            output_filename = self._args.output
        else:
            output_filename = generator_class.DEFAULT_FILENAME

        if self._args.observations_from_file:
            segments = [self._load_observations_from_file()]
        else:
            segments = self._get_segments_from_bvhs()
            if self._args.split_sensitivity:
                segments = self._split_segments_by_sensitivity(segments)

        if self._args.interpolate:
            segments = [self._interpolate_segment(segment)
                        for segment in segments]

        out = open(output_filename, "w")
        generator = generator_class(out, self._args)
        generator.generate(segments)
        out.close()

        print("Plotted %d observations in %d segments to file %s" % (
            sum([len(segment) for segment in segments]),
            len(segments), output_filename))

    def _load_observations_from_file(self):
        result = []
        for line in open(self._args.observations_from_file).readlines():
            observation = list(map(float, line.split(" ")))
            result.append(observation)
        return result

    def _get_segments_from_bvhs(self):
        return [self._get_observations_from_bvh(bvh_reader)
                for bvh_reader in self._selected_bvhs()]

    def _selected_bvhs(self):
        all_bvhs = self._experiment.bvh_reader.get_readers()
        if self._args.select_bvh:
            return [bvh_reader for bvh_reader in all_bvhs
                    if self._bvh_is_selected(bvh_reader.filename)]
        else:
            return all_bvhs

    def _bvh_is_selected(self, filename):
        return re.match(self._args.select_bvh, filename)

    def _get_observations_from_bvh(self, bvh_reader):
        if self._args.plot_joint_worldpos:
            return self._track_joint_worldpos(bvh_reader)
        else:
            return self._experiment.student.normalized_observed_reductions[
                bvh_reader.start_index : bvh_reader.end_index]

    def _track_joint_worldpos(self, bvh_reader):
        path = [self._get_worldpos(bvh_reader, n)
                for n in range(bvh_reader.get_num_frames())]
        path = self._normalize_vertices(path)
        return path

    def _normalize_vertices(self, vertices):
        return [self._normalize_vector(v) for v in vertices]

    def _normalize_vector(self, v):
        v = self._experiment.bvh_reader.normalize_vector(v)
        return (v + [1,1,1]) / 2

    def _get_worldpos(self, bvh_reader, n):
        frame = bvh_reader.frames[n]
        bvh_reader.get_hierarchy().set_pose_from_frame(self._experiment.pose, frame)
        return self._experiment.pose.get_joint(self._args.plot_joint_worldpos).get_vertex()

    def _split_segments_by_sensitivity(self, segments):
        result = []
        for observations in segments:
            result += self._split_observations_by_sensitivity(observations)
        return result

    def _split_observations_by_sensitivity(self, observations):
        segments = []
        segment = []
        previous_observation = None
        for observation in observations:
            if previous_observation is not None and \
                    numpy.linalg.norm(observation - previous_observation) > self._args.split_sensitivity:
                segments.append(segment)
                segment = []
            segment.append(observation)
            previous_observation = observation
        if len(segment) > 0:
            segments.append(segment)
        return segments

    def _interpolate_segment(self, segment):
        try:
            return interpolation.interpolate(segment, self._args.interpolation_resolution)
        except interpolation.InterpolationException as exception:
            print("WARNING: interpolation failed: %s" % exception)
            return segment

class Generator:
    def __init__(self, out, args):
        self._out = out
        self._args = args

    def _write(self, string):
        print(string, file=self._out)

class gnuplotGenerator(Generator):
    DEFAULT_FILENAME = "observations.dat"

    def generate(self, segments):
        for observations in segments:
            for observation in observations:
                print(" ".join([str(value) for value in observation]), file=self._out)
            print(file=self._out)

        if self._args.segments_output:
            n = 0
            for segment in segments:
                out = open(self._args.segments_output % n, "w")
                for observation in segment:
                    print(" ".join([str(value) for value in observation]), file=out)
                out.close()
                n += 1

class svgGenerator(Generator):
    DEFAULT_FILENAME = "observations.svg"

    def generate(self, segments):
        if self._args.plot_dimensions:
            self._dimensions = [int(string) for string in self._args.plot_dimensions.split(",")]
        else:
            self._dimensions = [0, 1]

        self._explored_range = 1.0 + self._args.explore_beyond_observations
        self._explored_min = .5 - self._explored_range/2
        self._explored_max = .5 + self._explored_range/2

        self._generate_header()
        for segment in segments:
            self._generate_segment(segment)
        self._generate_footer()

    def _generate_header(self):
        self._write('<svg xmlns="http://www.w3.org/2000/svg" version="1.1">\n')
        if self._args.background_color:
            self._write('<rect width="%f" height="%f" fill="%s" />' % (
                    self._args.plot_width, self._args.plot_height, self._args.background_color))
        else:
            self._write('<rect width="%f" height="%f" style="stroke-width:0;stroke:black;fill:none" />' % (
                    self._args.plot_width, self._args.plot_height))
        self._write('<g>\n')

    def _generate_segment(self, segment):
        if len(self._dimensions) == 2:
            self._generate_path_2d(segment)
        elif len(self._dimensions) == 3:
            self._generate_path_3d(segment)
            if self._args.point_size > 0:
                self._generate_points_3d(segment)

    def _generate_path_2d(self, segment):
        path_attributes = 'style="stroke:%s;fill:none;stroke-width:%f;stroke-opacity:%f"' % (
            self._args.stroke_color,
            self._args.stroke_width,
            self._args.stroke_opacity)
        if self._args.stroke_dasharray:
            path_attributes += ' stroke-dasharray="%s"' % self._args.stroke_dasharray
        self._write('<path %s d="M %s' % (
                path_attributes,
                self._whitespace_separated_path_coordinates(segment[0])))
        for observation in segment[1:]:
            self._write(' L %s' % self._whitespace_separated_path_coordinates(observation))
        self._write('" />\n')

    def _generate_path_3d(self, segment):
        previous_observation = segment[0]
        for observation in segment[1:]:
            z = self._depth_value(observation)
            stroke_width = max(self._args.stroke_width_min,
                               z * self._args.stroke_width)
            opacity = self._args.stroke_opacity * z
            self._write('<path '''
                    'style="stroke:%s;fill:none;stroke-width:%f;stroke-opacity:%f" '''
                    'd="M %s L %s" />' % (
                    self._args.stroke_color,
                    stroke_width,
                    opacity,
                    self._whitespace_separated_path_coordinates(previous_observation),
                    self._whitespace_separated_path_coordinates(observation)))
            previous_observation = observation

    def _generate_points_3d(self, segment):
        for observation in segment:
            cx, cy = self._path_coordinates(observation)
            z = self._depth_value(observation)
            radius = max(self._args.point_size_min,
                         z * self._args.point_size)
            opacity = z
            self._write('<circle cx="%f" cy="%f" r="%f" style="fill:%s;stroke:none;fill-opacity:%f" />' % (
                    cx, cy, radius, self._args.stroke_color, opacity))

    def _depth_value(self, observation):
        return pow((1 - min(observation[2], 1)), .8)

    def _whitespace_separated_path_coordinates(self, observation):
        px, py = self._path_coordinates(observation)
        return "%s %s" % (px, py)

    def _path_coordinates(self, observation):
        px = self._args.plot_width * (
            observation[self._dimensions[0]] - self._explored_min) / self._explored_range
        py = self._args.plot_height * (
            observation[self._dimensions[1]] - self._explored_min) / self._explored_range
        return px, py

    def _generate_footer(self):
        self._write('</g>\n')
        self._write('</svg>\n')


DimensionalityReductionExperiment.add_parser_arguments(parser)
experiment = DimensionalityReductionExperiment(parser)
experiment._load_model()
plotter = ObservationsPlotter(experiment)
plotter.plot()

