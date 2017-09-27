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

ENTITY_ARGS = "-r quaternion --friction --translate --confinement"
SKELETON_DEFINITION = "scenes/pn-01.22_z_up_xyz_skeleton.bvh"
NUM_REDUCED_DIMENSIONS = 7
Z_UP = True
FLOOR = True
MAX_NOVELTY = 4#1.4
SLIDER_PRECISION = 1000
MAX_LEARNING_RATE = 0.01
MAX_RECALL_RECENCY_SIZE = 60

from argparse import ArgumentParser
import numpy
import random
import math
import logging
from PyQt4 import QtGui, QtCore

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")
from application import Application, Avatar, BaseUiWindow, Memory, Recall, set_up_logging
from entities.hierarchical import Entity
from bvh.bvh_reader import BvhReader
from dimensionality_reduction.behavior import Behavior
from dimensionality_reduction.behaviors.improvise import ImproviseParameters, Improvise
from dimensionality_reduction.factory import DimensionalityReductionFactory
from ui.parameters_form import ParametersForm
import storage
from chaining import Chainer
from stopwatch import Stopwatch

parser = ArgumentParser()
parser.add_argument("--model", choices=MODELS, default="pca")
parser.add_argument("--with-ui", action="store_true")
parser.add_argument("--recall-amount", type=float, default=0)
parser.add_argument("--recall-duration", type=float, default=3)
parser.add_argument("--reverse-recall-probability", type=float, default=0)
parser.add_argument("--recall-recency-size", type=float, default=10.)
parser.add_argument("--recall-recency-bias", type=float, default=1.)
parser.add_argument("--learning-rate", type=float, default=0.0)
parser.add_argument("--memorize", action="store_true")
parser.add_argument("--auto-friction", action="store_true")
parser.add_argument("--verbose", action="store_true")
parser.add_argument("--memory")
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
        self._add_reset_translation_action()
        self._create_memory_menu()
        self._add_learning_rate_control()
        self._add_memory_size_label()
        self._add_memorize_control()
        self._add_recall_amount_control()
        self._add_auto_switch_control()
        self._add_recall_recency_size_control()
        self._add_recall_recency_bias_control()
        self._add_model_control()
        self._add_auto_friction_control()
        self._add_friction_control()
        self._add_confinement_control()
        self._add_confinement_rate_control()
        self._add_max_angular_step_control()
        self._add_improvise_parameters_form()
        self._add_noise_control()
        self._add_input_only_control()
        master_behavior.on_recall_amount_changed = self._update_recall_amount_slider
        memory.on_frames_changed = self._update_memory_size_label
        memory.on_frames_changed()

    def _add_reset_translation_action(self):
        action = QtGui.QAction("Reset translation", self)
        action.triggered.connect(master_behavior.reset_translation)
        self._main_menu.addAction(action)
        
    def _create_memory_menu(self):
        self._memory_menu = self._menu_bar.addMenu("Memory")
        self._add_clear_memory_action()
        self._add_load_memory_action()
        self._add_save_memory_action()

    def _add_clear_memory_action(self):
        def clear_memory():
            recall_behavior.reset()
            memory.clear()
            
        action = QtGui.QAction("Clear memory", self)
        action.triggered.connect(clear_memory)
        self._memory_menu.addAction(action)

    def _add_save_memory_action(self):
        def save_memory():
            filename = QtGui.QFileDialog.getSaveFileName(self, "Save memory", filter="Memory (*.mem)")
            if filename:
                storage.save(memory.get_frames(), filename)
                
        action = QtGui.QAction("Save memory", self)
        action.triggered.connect(save_memory)
        self._memory_menu.addAction(action)

    def _add_load_memory_action(self):
        def load_memory():
            filename = QtGui.QFileDialog.getLoadFileName(self, "Load memory", filter="Memory (*.mem)")
            if filename:
                memory.set_frames(storage.load(filename))
                recall_behavior.reset()
                
        action = QtGui.QAction("Load memory", self)
        action.triggered.connect(load_memory)
        self._memory_menu.addAction(action)

    def _add_memory_size_label(self):
        self._control_layout.add_label("Memory size")
        self._memory_size_label = QtGui.QLabel("")
        self._control_layout.add_control_widget(self._memory_size_label)

    def _update_memory_size_label(self):
        self._memory_size_label.setText("%d" % memory.get_num_frames())
        
    def _add_learning_rate_control(self):
        self._control_layout.add_slider_row(
            "Learning rate", MAX_LEARNING_RATE, args.learning_rate,
            students["autoencoder"].set_learning_rate)
        
    def _add_memorize_control(self):
        def on_changed_state(checkbox):
            master_behavior.memorize = checkbox.isChecked()
            
        self._control_layout.add_label("Memorize")
        checkbox = QtGui.QCheckBox()
        checkbox.setChecked(args.memorize)
        checkbox.stateChanged.connect(lambda: on_changed_state(checkbox))
        self._control_layout.add_control_widget(checkbox)

    def _add_recall_amount_control(self):
        self._recall_amount_slider = self._control_layout.add_slider_row(
            "Recall amount", 1., args.recall_amount,
            master_behavior.set_recall_amount)
        
    def _update_recall_amount_slider(self):
        # TODO: move logic to control_layout - this version doesn't take max value into account
        self._recall_amount_slider.setValue(master_behavior.get_recall_amount() * SLIDER_PRECISION)
        
    def _add_auto_switch_control(self):
        def on_changed_state(checkbox):
            master_behavior.set_auto_switch_enabled(checkbox.isChecked())
            self._recall_amount_slider.setEnabled(not checkbox.isChecked())

        self._control_layout.add_label("Auto switch")
        checkbox = QtGui.QCheckBox()
        checkbox.stateChanged.connect(lambda: on_changed_state(checkbox))
        self._control_layout.add_control_widget(checkbox)        

    def _add_recall_recency_size_control(self):
        self._control_layout.add_slider_row(
            "Recency size (s)", MAX_RECALL_RECENCY_SIZE, args.recall_recency_size,
            recall_behavior.set_recall_recency_size,
            label_precision=1)

    def _add_recall_recency_bias_control(self):
        self._control_layout.add_slider_row(
            "Recency bias", 1., args.recall_recency_bias,
            recall_behavior.set_recall_recency_bias,
            label_precision=1)
        
    def _add_max_angular_step_control(self):
        self._control_layout.add_slider_row(
            "Max angular step", 1., args.max_angular_step, set_max_angular_step)
        
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

    def _add_confinement_control(self):
        def on_changed_state(checkbox):
            master_entity.set_confinement(checkbox.isChecked())

        self._control_layout.add_label("Confinement")
        checkbox = QtGui.QCheckBox()
        checkbox.setEnabled(True)
        checkbox.setChecked(True)
        checkbox.stateChanged.connect(lambda: on_changed_state(checkbox))
        self._application.on_confinement_changed = lambda value: checkbox.setChecked(value)
        self._control_layout.add_control_widget(checkbox)
        
    def _add_confinement_rate_control(self):
        self._control_layout.add_slider_row(
            "Confinement rate", .1, .01, master_entity.set_confinement_rate)

    def _add_improvise_parameters_form(self):
        parameters_form = ParametersForm(improvise_params, control_layout=self._control_layout)
        
    def _add_noise_control(self):
        self._control_layout.add_slider_row(
            "Noise amount", .01, 0., master_behavior.set_noise_amount)

    def _add_input_only_control(self):
        def on_changed_state(checkbox):
            master_behavior.input_only = checkbox.isChecked()

        self._control_layout.add_label("Input only")
        checkbox = QtGui.QCheckBox()
        checkbox.stateChanged.connect(lambda: on_changed_state(checkbox))
        self._control_layout.add_control_widget(checkbox)

    def sizeHint(self):
        return QtCore.QSize(500, 0)        

class MasterBehavior(Behavior):
    def __init__(self):
        Behavior.__init__(self)
        self._recall_amount = args.recall_amount
        self.memorize = args.memorize
        self.auto_friction = args.auto_friction
        self._auto_switch_enabled = False
        self.input_only = False
        self._input = None
        self._noise_amount = 0
        self.reset_translation()
        self._stopwatch = Stopwatch()
        self._stopwatch.start()

    def set_noise_amount(self, amount):
        self._noise_amount = amount
        
    def reset_translation(self):
        master_entity.reset_constrainers()
        self._chainer = Chainer()
        self._chainer.put(numpy.zeros(3))
        self._chainer.get()
        self._chainer.switch_source()
        self._selector = Selector(self._chainer.switch_source)

    def on_recall_amount_changed(self):
        pass
    
    def set_recall_amount(self, recall_amount):
        self._recall_amount = recall_amount

    def get_recall_amount(self):
        return self._recall_amount
    
    def set_model(self, model_name):
        self._improvise = improvise_behaviors[model_name]
        self._chainer.switch_source()

    def proceed(self, time_increment):
        if self._noise_amount > 0:
            students["autoencoder"].add_noise(self._noise_amount)
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

    def set_auto_switch_enabled(self, value):
        self._auto_switch_enabled = value
        
    def get_output(self):
        if self.input_only:
            return self._input

        if self._auto_switch_enabled:
            self._recall_amount = self._get_auto_switch_recall_amount()
            self.on_recall_amount_changed()
            
        improvise_output = self._get_improvise_output()
        recall_output = recall_behavior.get_output()
        
        if args.verbose:
            self._print_output_info("improvise_output", improvise_output)
            self._print_output_info("recall_output", recall_output)
            
        if recall_output is None:
            if self._recall_amount > 0:
                application.print_and_log("WARNING: recall amount > 0 but no recall output")
            translation = self._pass_through_selector_to_update_its_state(
                get_translation(improvise_output))
            orientations = get_orientations(improvise_output)
        else:
            translation = self._selector.select(
                get_translation(improvise_output),
                get_translation(recall_output),
                self._recall_amount)
            orientations = get_orientations(
                master_entity.interpolate(improvise_output, recall_output, self._recall_amount))
                
        self._chainer.put(translation)
        translation = self._chainer.get()
        output = combine_translation_and_orientations(translation, orientations)
        
        return output

    def _pass_through_selector_to_update_its_state(self, value):
        return self._selector.select(value, None, 0)
    
    def _get_auto_switch_recall_amount(self):
        return (math.sin(self._stopwatch.get_elapsed_time() * .5) + 1) / 2
    
    def _print_output_info(self, name, output):
        if output is None:
            return
        root_quaternion = output[0:4]
        print "%s root: %s" % (name, root_quaternion)
    
    def _get_improvise_output(self):
        reduction = self._improvise.get_reduction()
        if reduction is None:
            return None
        return student.inverse_transform(numpy.array([reduction]))[0]

def get_translation(parameters):
    return parameters[0:3]

def get_orientations(parameters):
    return parameters[3:]

def combine_translation_and_orientations(translation, orientations):
    return numpy.array(list(translation) + list(orientations))

class RecallBehavior(Behavior):
    interpolation_duration = 1.0
    IDLE = "IDLE"
    NORMAL = "NORMAL"
    CROSSFADE = "CROSSFADE"
    
    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._recall_num_frames = int(round(args.recall_duration * args.frame_rate))
        self._interpolation_num_frames = int(round(self.interpolation_duration * args.frame_rate))
        self._recall_num_frames_including_interpolation = self._recall_num_frames + \
                                                          2 * self._interpolation_num_frames
        self.set_recall_recency_size(args.recall_recency_size)
        self.set_recall_recency_bias(args.recall_recency_bias)
        self.reset()

    def set_recall_recency_size(self, duration):
        self._recall_recency_num_frames = int(round(duration) * args.frame_rate)

    def set_recall_recency_bias(self, value):
        self._recall_recency_bias = value
        
    def reset(self):
        self._logger.debug("reset()")
        self._initialize_state(self.IDLE)
        self._output = None
        self._chainer = Chainer()

    def _initialize_state(self, state):
        self._logger.debug("_initialize_state(%s)" % state)
        self._state = state
        self._state_frames = 0
        if state == self.NORMAL:
            self._current_recall = self._next_recall
        elif state == self.CROSSFADE:
            self._selector = Selector(self._chainer.switch_source)
            self._next_recall = self._create_recall()
            self._interpolation_crossed_halfway = False

    def _create_recall(self):
        self._logger.debug("_create_recall()")
        if random.random() < self._recall_recency_bias:
            recency_num_frames = self._recall_recency_num_frames
            self._logger.debug("recall with recency")
        else:
            self._logger.debug("recall from entire memory")
            recency_num_frames = None
            
        return memory.create_random_recall(
            self._recall_num_frames_including_interpolation,
            recency_num_frames=recency_num_frames)

    def proceed(self, time_increment):
        self._logger.debug("proceed(%s)" % time_increment)
        self._remaining_frames_to_process = int(round(time_increment * args.frame_rate))
        self._logger.debug("_remaining_frames_to_process=%s" % self._remaining_frames_to_process)
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
        self._logger.debug("_proceed_in_idle()")
        if memory.get_num_frames() >= self._recall_num_frames_including_interpolation:
            self._next_recall = self._create_recall()
            self._initialize_state(self.NORMAL)
        else:
            self._remaining_frames_to_process = 0

    def _proceed_in_normal(self):
        self._logger.debug("_proceed_in_normal()")
        remaining_frames_in_state = self._recall_num_frames - self._state_frames
        self._logger.debug("remaining_frames_in_state=%s" % remaining_frames_in_state)
        if remaining_frames_in_state == 0:
            self._initialize_state(self.CROSSFADE)
            return
        
        frames_to_process = min(self._remaining_frames_to_process, remaining_frames_in_state)
        self._logger.debug("frames_to_process=%s" % frames_to_process)
        self._current_recall.proceed(frames_to_process)

        output = self._pass_through_interpolation_to_update_its_state(
            self._current_recall.get_output())
        
        translation = get_translation(output)
        orientations = get_orientations(output)
        self._chainer.put(translation)
        translation = self._chainer.get()
        self._output = combine_translation_and_orientations(translation, orientations)
        
        self._state_frames += frames_to_process
        self._remaining_frames_to_process -= frames_to_process

    def _pass_through_interpolation_to_update_its_state(self, output):
        return recall_entity.interpolate(output, output, 0)

    def _proceed_in_crossfade(self):
        self._logger.debug("_proceed_in_crossfade()")
        remaining_frames_in_state = self._interpolation_num_frames - self._state_frames
        self._logger.debug("remaining_frames_in_state=%s" % remaining_frames_in_state)
        if remaining_frames_in_state == 0:
            self._initialize_state(self.NORMAL)
            return
                
        frames_to_process = min(self._remaining_frames_to_process, remaining_frames_in_state)
        self._logger.debug("frames_to_process=%s" % frames_to_process)
        self._current_recall.proceed(frames_to_process)
        self._next_recall.proceed(frames_to_process)
        
        from_output = self._current_recall.get_output()
        to_output = self._next_recall.get_output()
        relative_cursor = float(self._state_frames) / self._interpolation_num_frames
        amount = 1 - (math.sin((relative_cursor + .5) * math.pi) + 1) / 2

        translation = self._selector.select(
            get_translation(from_output),
            get_translation(to_output),
            amount)
        self._chainer.put(translation)
        translation = self._chainer.get()
        orientations = get_orientations(recall_entity.interpolate(from_output, to_output, amount))
        self._output = combine_translation_and_orientations(translation, orientations)

        self._state_frames += frames_to_process
        self._remaining_frames_to_process -= frames_to_process

    def get_output(self):
        return self._output

class Selector:
    def __init__(self, on_switch):
        self._previous_amount = None
        self._on_switch = on_switch
        
    def select(self, from_value, to_value, amount):
        if self._previous_amount is not None and int(round(amount)) != int(round(self._previous_amount)):
            self._on_switch()
        self._previous_amount = amount
        if int(round(amount)) == 0:
            return from_value
        else:
            return to_value
        
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

set_up_logging()

index = 0
memory = Memory()
if args.memory:
    memory.set_frames(storage.load(args.memory))
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
    qt_app.exec_()
else:
    application.initialize()
    application.main_loop()
