#!/usr/bin/env python

STUDENT_MODEL_PATH = "profiles/dimensionality_reduction/valencia_pn_autoencoder.model"
SKELETON_DEFINITION = "scenes/pn-01.22_skeleton.bvh"
DIMENSIONALITY_REDUCTION_TYPE = "AutoEncoder"
DIMENSIONALITY_REDUCTION_ARGS = "--num-hidden-nodes=0 --learning-rate=0.005 --tied-weights"
ENTITY_ARGS = "-r quaternion --friction --translate"

NUM_REDUCED_DIMENSIONS = 7
Z_UP = False
FLOOR = True
MAX_NOVELTY = 1.4

from argparse import ArgumentParser

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")
from application import Application, Avatar
from entities.hierarchical import Entity
from bvh.bvh_reader import BvhReader
from dimensionality_reduction.behaviors.improvise import ImproviseParameters, Improvise
from dimensionality_reduction.factory import DimensionalityReductionFactory

parser = ArgumentParser()
Application.add_parser_arguments(parser)
ImproviseParameters().add_parser_arguments(parser)
args = parser.parse_args()
            
bvh_reader = BvhReader(SKELETON_DEFINITION)
bvh_reader.read()
entity_args_strings = ENTITY_ARGS.split()
entity_args = parser.parse_args(entity_args_strings)

def create_entity():
    return Entity(bvh_reader, pose, FLOOR, Z_UP, entity_args)

pose = bvh_reader.get_hierarchy().create_pose()
entity = create_entity()

num_input_dimensions = entity.get_value_length()
student = DimensionalityReductionFactory.create(
    DIMENSIONALITY_REDUCTION_TYPE, num_input_dimensions, NUM_REDUCED_DIMENSIONS, DIMENSIONALITY_REDUCTION_ARGS)
student.load(STUDENT_MODEL_PATH)

improvise_params = ImproviseParameters()
preferred_location = None
improvise = Improvise(
    student,
    student.num_reduced_dimensions,
    improvise_params,
    preferred_location,
    MAX_NOVELTY)
index = 0
avatar = Avatar(index, entity, improvise)

avatars = [avatar]

application = Application(student, avatars, args, receive_from_pn=True, create_entity=create_entity)
application.initialize()
application.run()
