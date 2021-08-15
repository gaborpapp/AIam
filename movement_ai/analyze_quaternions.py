#!/usr/bin/env python

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")

from argparse import ArgumentParser
from bvh.bvh_reader import bvh_reader as bvh_reader_module
from angle_parameters import quaternion_from_euler
from collections import defaultdict

class QuaternionAnalyzer:
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("bvh")

    def __init__(self, args):
        self.args = args
        self.bvh_reader = bvh_reader_module.BvhReader(args.bvh)
        self.bvh_reader.read()

    def analyze(self):
        self._count_and_sum_by_hemisphere()
        self._identify_hemisphere_profiles()
        self._print_results()

    def _count_and_sum_by_hemisphere(self):
        self._hemisphere_counts = defaultdict(
            lambda: {"+": 0, "-": 0})
        for n in range(self.bvh_reader.skeleton.num_frames):
            root_joint = self.bvh_reader.skeleton.get_root_joint(n)
            self._process_joint_recurse(root_joint)

    def _identify_hemisphere_profiles(self):
        self._hemisphere_profiles = {}
        for joint_name, hemisphere_count in self._hemisphere_counts.items():
            self._hemisphere_profiles[joint_name] = self._hemisphere_profile(
                hemisphere_count)

    def _hemisphere_profile(self, hemisphere_count):
        if hemisphere_count["+"] > 0 and hemisphere_count["-"] > 0:
            return "double_cover"
        elif hemisphere_count["+"] > 0:
            return "plus_only"
        elif hemisphere_count["-"] > 0:
            return "minus_only"
        else:
            return "none"

    def _print_results(self):
        for profile in ["double_cover", "plus_only", "minus_only", "none"]:
            self._print_result_for_profile(profile)

    def _print_result_for_profile(self, profile):
        joint_names = [joint_name
                       for joint_name, value in self._hemisphere_profiles.items()
                       if value == profile]
        print(profile)
        for joint_name in joint_names:
            print("  %s: %s" % (joint_name, self._hemisphere_counts[joint_name]))

    def _process_joint_recurse(self, joint):
        if joint.rotation:
            self._process_rotation(joint)
        for child in joint.children:
            self._process_joint_recurse(child)

    def _process_rotation(self, joint):
        quaternion = quaternion_from_euler(
            *joint.rotation.angles, axes=joint.rotation.axes)
        if quaternion[0] < 0.0:
            sign = "-"
        else:
            sign = "+"
        self._hemisphere_counts[joint.name][sign] += 1

parser = ArgumentParser()
QuaternionAnalyzer.add_parser_arguments(parser)
args = parser.parse_args()
QuaternionAnalyzer(args).analyze()
