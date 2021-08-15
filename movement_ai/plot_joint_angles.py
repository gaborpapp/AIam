#!/usr/bin/env python

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")

from argparse import ArgumentParser
from bvh import bvh_reader as bvh_reader_module
import math
from PIL import Image
import numpy

class JointAnglePlotter:
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("bvh")
        parser.add_argument("output")
        parser.add_argument("-radius", type=int, default=100)
        parser.add_argument("-spacing", type=int, default=10)
        parser.add_argument("--count-unique-angles", action="store_true")

    def __init__(self, args):
        self.args = args
        self.bvh_reader = bvh_reader_module.BvhReader(args.bvh)
        self.bvh_reader.read()
        self._pose = self.bvh_reader.create_pose()

        self.width = self.args.spacing * 6 + self.args.radius * 6
        self.height = self.args.spacing * 2 + self.args.radius * 2
        self._create_outputs()

        self.dimension_plots = {}
        n = 0
        for axis in ["x", "y", "z"]:
            self.dimension_plots[axis] = {
                "cx": self.args.spacing * (1+n*2) + self.args.radius * (n*2) + self.args.radius,
                "cy": self.args.spacing + self.args.radius}
            n += 1

        if self.args.count_unique_angles:
            self.unique_angles = {}

    def _create_outputs(self):
        root_joint_definition = self.bvh_reader.get_hierarchy().get_root_joint_definition()
        self.outputs = []
        self._identify_joints_with_rotation(root_joint_definition)

        for output in self.outputs:
            image_buffer = numpy.empty(self.width * self.height * 3)
            image_buffer.fill(255)
            output["image_buffer"] = image_buffer
            if self.args.count_unique_angles:
                output["unique_angles"] = set()

    def _identify_joints_with_rotation(self, joint_definition):
        if joint_definition.has_rotation:
            joint_definition.index_with_rotation = len(self.outputs)
            self.outputs.append({"joint": joint_definition})
        for child_definition in joint_definition.child_definitions:
            self._identify_joints_with_rotation(child_definition)

    def plot(self):
        for frame in self.bvh_reader.frames:
            self.bvh_reader.get_hierarchy().set_pose_from_frame(self._pose, frame)
            root_joint = self._pose.get_root_joint()
            self._process_joint_recurse(root_joint)
        self._save_images()

        if self.args.count_unique_angles:
            self._print_unique_angles_results()

    def _save_images(self):
        n = 0
        for output in self.outputs:
            output_path = "%s%03d_%s.png" % (
                args.output, n, output["joint"].name)
            image = Image.fromstring("RGB", (self.width, self.height),
                                     data=self._array_to_string(output["image_buffer"]))
            image.save(output_path)
            n += 1

    def _array_to_string(self, xs):
        return "".join([chr(int(x)) for x in xs])

    def _process_joint_recurse(self, joint):
        if joint.definition.has_rotation:
            self._process_rotation(joint)
        for child in joint.children:
            self._process_joint_recurse(child)

    def _process_rotation(self, joint):
        image_buffer = self.outputs[joint.definition.index_with_rotation]["image_buffer"]
        for axis, angle in zip(joint.rotation.axes[1:], joint.rotation.angles):
            self._plot_angle(image_buffer, axis, angle)

        if self.args.count_unique_angles:
            self.outputs[joint.index_with_rotation]["unique_angles"].add(tuple(joint.rotation.angles))

    def _plot_angle(self, image_buffer, axis, angle):
        dimension_plot = self.dimension_plots[axis]
        x = int(dimension_plot["cx"] + self.args.radius * math.cos(angle))
        y = int(dimension_plot["cy"] + self.args.radius * math.sin(angle))
        p = (y * self.width + x) * 3
        image_buffer[p] = 0
        image_buffer[p+1] = 0
        image_buffer[p+2] = 0

    def _print_unique_angles_results(self):
        for output in self.outputs:
            print("%s %s" % (len(output["unique_angles"]), output["joint"].name))

parser = ArgumentParser()
JointAnglePlotter.add_parser_arguments(parser)
args = parser.parse_args()
JointAnglePlotter(args).plot()
