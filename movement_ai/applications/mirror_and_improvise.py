#!/usr/bin/env python

# STUDENT_MODEL_PATH = "profiles/dimensionality_reduction/valencia_pn_autoencoder.model"
# SKELETON_DEFINITION = "scenes/pn-01.22_skeleton.bvh"
# DIMENSIONALITY_REDUCTION_TYPE = "AutoEncoder"
# DIMENSIONALITY_REDUCTION_ARGS = "--num-hidden-nodes=0 --learning-rate=0.005"
# ENTITY_ARGS = "-r quaternion --friction --translate"

STUDENT_MODEL_PATH = "profiles/dimensionality_reduction/valencia_pn.model"
SKELETON_DEFINITION = "scenes/pn-01.22_skeleton.bvh"
DIMENSIONALITY_REDUCTION_TYPE = "KernelPCA"
DIMENSIONALITY_REDUCTION_ARGS = ""
ENTITY_ARGS = "-r quaternion --friction"

NUM_REDUCED_DIMENSIONS = 7
Z_UP = False
FLOOR = True
MAX_NOVELTY = 1.4

from argparse import ArgumentParser
import threading
import numpy

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")
from application import Application, Avatar
from entities.hierarchical import Entity
from bvh.bvh_reader import BvhReader
from dimensionality_reduction.behavior import Behavior
from dimensionality_reduction.behaviors.improvise import ImproviseParameters, Improvise
from dimensionality_reduction.factory import DimensionalityReductionFactory
import tracking.pn.receiver

parser = ArgumentParser()
parser.add_argument("--pn-host", default="localhost")
parser.add_argument("--pn-port", type=int, default=tracking.pn.receiver.SERVER_PORT_BVH)
Application.add_parser_arguments(parser)
ImproviseParameters().add_parser_arguments(parser)
args = parser.parse_args()
            
bvh_reader = BvhReader(SKELETON_DEFINITION)
bvh_reader.read()
entity_args_strings = ENTITY_ARGS.split()
entity_args = parser.parse_args(entity_args_strings)

pose = bvh_reader.get_hierarchy().create_pose()
entity = Entity(bvh_reader, pose, FLOOR, Z_UP, entity_args)

num_input_dimensions = entity.get_value_length()
student = DimensionalityReductionFactory.create(
    DIMENSIONALITY_REDUCTION_TYPE, num_input_dimensions, NUM_REDUCED_DIMENSIONS, DIMENSIONALITY_REDUCTION_ARGS)
student.load(STUDENT_MODEL_PATH)

class MetaBehaviour(Behavior):
    MIRROR = "MIRROR"
    IMPROVISE = "IMPROVISE"
    
    normal_duration = 3.0
    interpolation_duration = 1.0
    
    def __init__(self, improvise):
        Behavior.__init__(self)
        self._improvise = improvise
        self._input = None
        self._output = None
        self._initialize_state(self.MIRROR)

    def _initialize_state(self, state):
        self._current_state = state
        self._state_time = 0
        self._interpolating = False

    def proceed(self, time_increment):
        self._remaining_time_to_process = time_increment
        while self._remaining_time_to_process > 0:
            self._proceed_within_state()

    def _proceed_within_state(self):
        if self._interpolating:
            return self._proceed_within_interpolation()
        else:
            return self._proceed_within_normal_state()

    def _switch_to_next_state(self):
        next_state = self._select_next_state()
        self._initialize_state(next_state)

    def _select_next_state(self):
        if self._current_state == self.MIRROR:
            return self.IMPROVISE
        else:
            return self.MIRROR
        
    def _proceed_within_interpolation(self):
        remaining_time_in_state = self.interpolation_duration - self._state_time
        if remaining_time_in_state == 0:
            self._switch_to_next_state()
            return
        time_to_process = min(self._remaining_time_to_process, remaining_time_in_state)
        self._improvise.proceed(time_to_process)
        if self._current_state == self.MIRROR:
            input_amount = 1 - self._state_time / self.interpolation_duration
        else:
            input_amount = self._state_time / self.interpolation_duration
        improvise_amount = 1 - input_amount
        entity.set_friction(improvise_amount > 0.5)
        self._output = entity.interpolate(self._input, self._get_improvise_output(), improvise_amount)
        self._state_time += time_to_process
        self._remaining_time_to_process -= time_to_process
                
    def _proceed_within_normal_state(self):
        remaining_time_in_state = self.normal_duration - self._state_time
        if remaining_time_in_state == 0:
            self._interpolating = True
            self._state_time = 0
            return
        time_to_process = min(self._remaining_time_to_process, remaining_time_in_state)
        self._improvise.proceed(time_to_process)
        if self._current_state == self.IMPROVISE:
            entity.set_friction(True)
            self._output = self._get_improvise_output()
        elif self._current_state == self.MIRROR:
            entity.set_friction(False)
            self._output = self._input
        self._state_time += time_to_process
        self._remaining_time_to_process -= time_to_process

    def sends_output(self):
        return True

    def on_input(self, input_):
        self._input = input_
        
    def get_output(self):
        return self._output

    def _get_improvise_output(self):
        reduction = self._improvise.get_reduction()
        return student.inverse_transform(numpy.array([reduction]))[0]
    
improvise_params = ImproviseParameters()
preferred_location = None
improvise = Improvise(
    student,
    student.num_reduced_dimensions,
    improvise_params,
    preferred_location,
    MAX_NOVELTY)
index = 0
avatar = Avatar(index, entity, MetaBehaviour(improvise))

avatars = [avatar]

application = Application(student, avatars, args)

def receive_from_pn(pn_entity):
    for frame in pn_receiver.get_frames():
        input_from_pn = pn_entity.get_value_from_frame(frame)
        application.set_input(input_from_pn)
        
pn_receiver = tracking.pn.receiver.PnReceiver()
print "connecting to PN server..."
pn_receiver.connect(args.pn_host, args.pn_port)
print "ok"
pn_pose = bvh_reader.get_hierarchy().create_pose()
pn_entity = Entity(bvh_reader, pn_pose, FLOOR, Z_UP, entity_args)
pn_receiver_thread = threading.Thread(target=lambda: receive_from_pn(pn_entity))
pn_receiver_thread.daemon = True
pn_receiver_thread.start()

application.run()
