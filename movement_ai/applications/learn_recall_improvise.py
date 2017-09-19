#!/usr/bin/env python

MODELS = ["autoencoder", "pca"]
MODELS_INFO = {
    "autoencoder": {
        "path": "profiles/dimensionality_reduction/valencia_pn_autoencoder_z_up.model",
        "dimensionality_reduction_type": "AutoEncoder",
        "dimensionality_reduction_args": "--num-hidden-nodes=0 --tied-weights"
        },

    "pca": {
        # "path": "profiles/dimensionality_reduction/valencia_pn_z_up.model",
        # "dimensionality_reduction_type": "KernelPCA",
        # "dimensionality_reduction_args": "--pca-kernel=rbf",
        
        "path": "profiles/dimensionality_reduction/valencia_pn_2017_09_z_up.model",
        "dimensionality_reduction_type": "KernelPCA",
        "dimensionality_reduction_args": "--pca-kernel=rbf"
        }
    }

ENTITY_ARGS = "-r quaternion --friction --translate"
SKELETON_DEFINITION = "scenes/pn-01.22_z_up_xyz_skeleton.bvh"
NUM_REDUCED_DIMENSIONS = 7
Z_UP = True
FLOOR = True
MAX_NOVELTY = 4#1.4
SLIDER_PRECISION = 1000
MAX_LEARNING_RATE = 0.01

from argparse import ArgumentParser
import numpy
import random
from PyQt4 import QtGui, QtCore

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")
from application import Application, Avatar, BaseUiWindow, Memory, Recall
from entities.hierarchical import Entity
from bvh.bvh_reader import BvhReader
from dimensionality_reduction.behavior import Behavior
from dimensionality_reduction.behaviors.improvise import ImproviseParameters, Improvise
from dimensionality_reduction.factory import DimensionalityReductionFactory
from ui.parameters_form import ParametersForm

parser = ArgumentParser()
parser.add_argument("--model", choices=MODELS, default="pca")
parser.add_argument("--with-ui", action="store_true")
parser.add_argument("--recall-amount", type=float, default=0)
parser.add_argument("--recall-duration", type=float, default=3)
parser.add_argument("--reverse-recall-probability", type=float, default=0)
parser.add_argument("--learning-rate", type=float, default=0.0)
parser.add_argument("--memorize", action="store_true")
parser.add_argument("--auto-friction", action="store_true")
Application.add_parser_arguments(parser)
ImproviseParameters().add_parser_arguments(parser)
args = parser.parse_args()
            
bvh_reader = BvhReader(SKELETON_DEFINITION)
bvh_reader.read()
entity_args_strings = ENTITY_ARGS.split()
entity_args = parser.parse_args(entity_args_strings)

def create_entity():
    return Entity(bvh_reader, bvh_reader.get_hierarchy().create_pose(), FLOOR, Z_UP, entity_args)

master_entity = create_entity()
recall_entity = create_entity()

def _create_and_load_student(model_name):
    model_info = MODELS_INFO[model_name]
    student = DimensionalityReductionFactory.create(
        model_info["dimensionality_reduction_type"],
        num_input_dimensions,
        NUM_REDUCED_DIMENSIONS,
        model_info["dimensionality_reduction_args"])
    student.load(model_info["path"])
    return student
    
num_input_dimensions = master_entity.get_value_length()
students = {
    model_name: _create_and_load_student(model_name)
    for model_name in MODELS}
students["autoencoder"].set_learning_rate(args.learning_rate)

def set_model(model_name):
    global student
    application.set_student(students[model_name])
    student = students[model_name]
    master_behavior.set_model(model_name)

def set_max_angular_step(max_angular_step):
    master_entity.set_max_angular_step(max_angular_step)
    recall_entity.set_max_angular_step(max_angular_step)
        
class UiWindow(BaseUiWindow):
    def __init__(self, master_behavior):
        super(UiWindow, self).__init__(application, master_behavior)
        self._create_memory_menu()
        self._add_learning_rate_control()
        self._add_memorize_control()
        self._add_recall_amount_control()
        self._add_model_control()
        self._add_auto_friction_control()
        self._add_friction_control()
        self._add_max_angular_step_control()
        self._add_improvise_parameters_form()
        self._add_input_only_control()

    def _create_memory_menu(self):
        self._memory_menu = self._menu_bar.addMenu("Memory")
        self._add_clear_memory_action()

    def _add_clear_memory_action(self):
        def clear_memory():
            recall_behavior.reset()
            memory.clear()
            
        action = QtGui.QAction("Clear memory", self)
        action.triggered.connect(clear_memory)
        self._memory_menu.addAction(action)
        
    def _add_learning_rate_control(self):
        def create_slider():
            slider = QtGui.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, SLIDER_PRECISION)
            slider.setSingleStep(1)
            slider.setValue(args.learning_rate / MAX_LEARNING_RATE * SLIDER_PRECISION)
            slider.valueChanged.connect(on_changed_value)
            return slider
    
        def on_changed_value(value):
            learning_rate = float(value) / SLIDER_PRECISION * MAX_LEARNING_RATE
            students["autoencoder"].set_learning_rate(learning_rate)

        self._control_layout.add_label("Learning rate")
        self._control_layout.add_control_widget(create_slider())
        
    def _add_memorize_control(self):
        def on_changed_state(checkbox):
            master_behavior.memorize = checkbox.isChecked()
            
        self._control_layout.add_label("Memorize")
        checkbox = QtGui.QCheckBox()
        checkbox.setChecked(args.memorize)
        checkbox.stateChanged.connect(lambda: on_changed_state(checkbox))
        self._control_layout.add_control_widget(checkbox)

    def _add_recall_amount_control(self):
        def create_slider():
            slider = QtGui.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, SLIDER_PRECISION)
            slider.setSingleStep(1)
            slider.setValue(args.recall_amount * SLIDER_PRECISION)
            slider.valueChanged.connect(on_changed_value)
            return slider

        def on_changed_value(value):
            recall_amount = float(value) / SLIDER_PRECISION
            master_behavior.set_recall_amount(recall_amount)

        self._control_layout.add_label("Recall amount")
        self._control_layout.add_control_widget(create_slider())
        
    def _add_max_angular_step_control(self):
        def create_slider():
            slider = QtGui.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, SLIDER_PRECISION)
            slider.setSingleStep(1)
            slider.setValue(args.max_angular_step * SLIDER_PRECISION)
            slider.valueChanged.connect(on_changed_value)
            return slider

        def on_changed_value(value):
            max_angular_step = float(value) / SLIDER_PRECISION
            set_max_angular_step(max_angular_step)

        self._control_layout.add_label("Max angular step")
        self._control_layout.add_control_widget(create_slider())
        
    def _add_model_control(self):
        def create_combobox():
            combobox = QtGui.QComboBox()
            for model_name in MODELS:
                combobox.addItem(model_name)
            combobox.activated.connect(on_activated)
            combobox.setCurrentIndex(combobox.findText(args.model))
            return combobox

        def on_activated(value):
            set_model(MODELS[value])

        self._control_layout.add_label("Model")
        self._control_layout.add_control_widget(create_combobox())
        
    def _add_auto_friction_control(self):
        def on_changed_state(checkbox):
            master_behavior.auto_friction = checkbox.isChecked()
            self._friction_checkbox.setEnabled(not master_behavior.auto_friction)

        self._control_layout.add_label("Auto friction")
        checkbox = QtGui.QCheckBox()
        checkbox.setChecked(args.auto_friction)
        checkbox.stateChanged.connect(lambda: on_changed_state(checkbox))
        self._control_layout.add_control_widget(checkbox)

    def _add_friction_control(self):
        def on_changed_state():
            master_entity.set_friction(self._friction_checkbox.isChecked())

        self._control_layout.add_label("Friction")
        self._friction_checkbox = QtGui.QCheckBox()
        self._friction_checkbox.setEnabled(not args.auto_friction)
        self._friction_checkbox.stateChanged.connect(on_changed_state)
        self._application.on_friction_changed = lambda value: self._friction_checkbox.setChecked(value)
        self._control_layout.add_control_widget(self._friction_checkbox)

    def _add_improvise_parameters_form(self):
        parameters_form = ParametersForm(improvise_params, control_layout=self._control_layout)

    def _add_input_only_control(self):
        def on_changed_state(checkbox):
            master_behavior.input_only = checkbox.isChecked()

        self._control_layout.add_label("Input only")
        checkbox = QtGui.QCheckBox()
        checkbox.stateChanged.connect(lambda: on_changed_state(checkbox))
        self._control_layout.add_control_widget(checkbox)

class MasterBehavior(Behavior):
    def __init__(self):
        Behavior.__init__(self)
        self._recall_amount = args.recall_amount
        self.memorize = args.memorize
        self.auto_friction = args.auto_friction
        self.input_only = False
        self._input = None

    def set_recall_amount(self, recall_amount):
        self._recall_amount = recall_amount
        
    def set_model(self, model_name):
        self._improvise = improvise_behaviors[model_name]

    def proceed(self, time_increment):
        self._improvise.proceed(time_increment)
        recall_behavior.proceed(time_increment)
        if self.auto_friction:
            if self._recall_amount < 0.5:
                self._set_master_entity_friction_and_update_ui(True)
            else:
                self._set_master_entity_friction_and_update_ui(False)

    def _set_master_entity_friction_and_update_ui(self, value):
        master_entity.set_friction(value)
        application.on_friction_changed(value)
                
    def sends_output(self):
        return True

    def on_input(self, input_):
        self._input = input_
        if self.memorize:
            memory.on_input(input_)
    
    def get_output(self):
        if self.input_only:
            return self._input
        
        improvise_output = self._get_improvise_output()
        recall_output = recall_behavior.get_output()
        if recall_output is None:
            if self._recall_amount > 0:
                print "WARNING: recall amount > 0 but no recall output"
            return improvise_output
        translation = self._get_translation(improvise_output)
        orientations = self._get_orientations(
            master_entity.interpolate(improvise_output, recall_output, self._recall_amount))
        output = self._combine_translation_and_orientation(translation, orientations)
        return output

    def _get_improvise_output(self):
        reduction = self._improvise.get_reduction()
        if reduction is None:
            return None
        return student.inverse_transform(numpy.array([reduction]))[0]

    def _get_translation(self, parameters):
        return parameters[0:3]

    def _get_orientations(self, parameters):
        return parameters[3:]

    def _combine_translation_and_orientation(self, translation, orientations):
        return numpy.array(list(translation) + list(orientations))

class RecallBehavior(Behavior):
    interpolation_duration = 1.0
    IDLE = "IDLE"
    NORMAL = "NORMAL"
    CROSSFADE = "CROSSFADE"
    
    def __init__(self):
        self._recall_num_frames = int(round(args.recall_duration * args.frame_rate))
        self._interpolation_num_frames = int(round(self.interpolation_duration * args.frame_rate))
        self._recall_num_frames_including_interpolation = self._recall_num_frames + \
                                                          2 * self._interpolation_num_frames
        self.reset()

    def reset(self):
        self._initialize_state(self.IDLE)
        self._output = None

    def _initialize_state(self, state):
        print state
        self._state = state
        self._state_frames = 0
        if state == self.NORMAL:
            self._current_recall = memory.create_random_recall(
                self._recall_num_frames_including_interpolation)
        elif state == self.CROSSFADE:
            self._next_recall = memory.create_random_recall(
                self._recall_num_frames_including_interpolation)
            self._interpolation_crossed_halfway = False

    def proceed(self, time_increment):
        self._remaining_frames_to_process = int(round(time_increment * args.frame_rate))
        while self._remaining_frames_to_process > 0:
            self._proceed_within_state()

    def _proceed_within_state(self):
        if self._state == self.IDLE:
            self._proceed_in_idle()
        elif self._state == self.NORMAL:
            self._proceed_in_normal()
        elif self._state == self.CROSSFADE:
            self._proceed_in_crossfade()

    def _proceed_in_idle(self):
        if memory.get_num_frames() >= self._recall_num_frames_including_interpolation:
            self._initialize_state(self.NORMAL)
        else:
            self._remaining_frames_to_process = 0

    def _proceed_in_normal(self):
        remaining_frames_in_state = self._recall_num_frames - self._state_frames
        if remaining_frames_in_state == 0:
            self._initialize_state(self.CROSSFADE)
            return
        
        frames_to_process = min(self._remaining_frames_to_process, remaining_frames_in_state)
        self._current_recall.proceed(frames_to_process)
        self._output = self._pass_through_interpolation_to_update_its_state(
            self._current_recall.get_output())
        
        self._state_frames += frames_to_process
        self._remaining_frames_to_process -= frames_to_process

    def _pass_through_interpolation_to_update_its_state(self, output):
        return recall_entity.interpolate(output, output, 0)

    def _proceed_in_crossfade(self):
        remaining_frames_in_state = self._interpolation_num_frames - self._state_frames
        if remaining_frames_in_state == 0:
            self._initialize_state(self.NORMAL)
            return
                
        frames_to_process = min(self._remaining_frames_to_process, remaining_frames_in_state)
        self._current_recall.proceed(frames_to_process)
        self._next_recall.proceed(frames_to_process)
        
        from_output = self._current_recall.get_output()
        to_output = self._next_recall.get_output()
        amount = float(self._state_frames) / self._interpolation_num_frames
        self._output = recall_entity.interpolate(from_output, to_output, amount)

        self._state_frames += frames_to_process
        self._remaining_frames_to_process -= frames_to_process

    def get_output(self):
        return self._output
        
def _create_improvise_behavior(model_name):
    preferred_location = None
    student = students[model_name]
    return Improvise(
        student,
        student.num_reduced_dimensions,
        improvise_params,
        preferred_location,
        MAX_NOVELTY)

improvise_params = ImproviseParameters()
improvise_behaviors = {
    model_name: _create_improvise_behavior(model_name)
    for model_name in MODELS}

index = 0
memory = Memory()
recall_behavior = RecallBehavior()
master_behavior = MasterBehavior() 
avatar = Avatar(index, master_entity, master_behavior)

avatars = [avatar]

application = Application(
    students[args.model], avatars, args, receive_from_pn=True, create_entity=create_entity)

set_model(args.model)
set_max_angular_step(args.max_angular_step)

if args.with_ui:
    qt_app = QtGui.QApplication(sys.argv)
    ui_window = UiWindow(master_behavior)
    ui_window.show()
    application.initialize()
    application.start_learning_thread()
    qt_app.exec_()
else:
    application.initialize()
    application.start_learning_thread()
    application.main_loop()
