#!/usr/bin/env python

MODELS = ["autoencoder", "pca"]
MODELS_INFO = {
    "autoencoder": {
        "path": "profiles/dimensionality_reduction/valencia_pn_autoencoder_z_up.model",
        "dimensionality_reduction_type": "AutoEncoder",
        "dimensionality_reduction_args": "--num-hidden-nodes=0 --tied-weights"
        },

    "pca": {
        # "path": "profiles/dimensionality_reduction/valencia_pn_2017_07.model",
        # "dimensionality_reduction_type": "KernelPCA",
        # "dimensionality_reduction_args": ""

        "path": "profiles/dimensionality_reduction/valencia_pn_z_up.model",
        "dimensionality_reduction_type": "KernelPCA",
        "dimensionality_reduction_args": "--pca-kernel=rbf"
        }
    }

ENTITY_ARGS = "-r quaternion --friction --translate --max-angular-step=0.15"
SKELETON_DEFINITION = "scenes/pn-01.22_z_up_xyz_skeleton.bvh"
NUM_REDUCED_DIMENSIONS = 7
Z_UP = True
FLOOR = True
MAX_NOVELTY = 4#1.4
SLIDER_PRECISION = 1000
MAX_DELAY_SECONDS = 10
MAX_LEARNING_RATE = 0.01

from argparse import ArgumentParser
import threading
import numpy
import random
import collections
from PyQt4 import QtGui, QtCore

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")
from application import Application, Avatar, BaseUiWindow
from entities.hierarchical import Entity
from bvh.bvh_reader import BvhReader
from dimensionality_reduction.behavior import Behavior
from dimensionality_reduction.behaviors.improvise import ImproviseParameters, Improvise
from dimensionality_reduction.factory import DimensionalityReductionFactory
import tracking.pn.receiver
from delay_shift import SmoothedDelayShift
from chaining import Chainer

parser = ArgumentParser()
parser.add_argument("--pn-host", default="localhost")
parser.add_argument("--pn-port", type=int, default=tracking.pn.receiver.SERVER_PORT_BVH)
parser.add_argument("--pn-convert-to-z-up", action="store_true")
parser.add_argument("--model", choices=MODELS, default="pca")
parser.add_argument("--pn-translation-offset")
parser.add_argument("--with-ui", action="store_true")
parser.add_argument("--enable-mirror", action="store_true")
parser.add_argument("--enable-recall", action="store_true")
parser.add_argument("--enable-improvise", action="store_true")
parser.add_argument("--mirror-weight", type=float, default=1.0)
parser.add_argument("--improvise-weight", type=float, default=1.0)
parser.add_argument("--recall-weight", type=float, default=1.0)
parser.add_argument("--mirror-duration", type=float, default=3)
parser.add_argument("--improvise-duration", type=float, default=3)
parser.add_argument("--recall-duration", type=float, default=3)
parser.add_argument("--delay-shift", type=float, default=0)
parser.add_argument("--reverse-recall-probability", type=float, default=0)
parser.add_argument("--io-blending-amount", type=float, default=1)
parser.add_argument("--learning-rate", type=float, default=0.0)
Application.add_parser_arguments(parser)
ImproviseParameters().add_parser_arguments(parser)
args = parser.parse_args()
            
bvh_reader = BvhReader(SKELETON_DEFINITION)
bvh_reader.read()
entity_args_strings = ENTITY_ARGS.split()
entity_args = parser.parse_args(entity_args_strings)

def create_entity():
    return Entity(bvh_reader, bvh_reader.get_hierarchy().create_pose(), FLOOR, Z_UP, entity_args)

switching_behavior_entity = create_entity()
master_entity = create_entity()

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
    for model_name in ["autoencoder", "pca"]}
students["autoencoder"].set_learning_rate(args.learning_rate)

def set_model(model_name):
    global student
    application.set_student = students[model_name]
    student = students[model_name]
    master_behavior.set_model(model_name)

class WeightedShuffler:
    def __init__(self, options, weights):
        self._options = options
        self._weights = weights
        self._weights_sum = sum(weights)

    def choice(self):
        r = random.random() * self._weights_sum
        for index, weight in enumerate(self._weights):
            r -= weight
            if r < 0:
                return self._options[index]

class Memory:
    def __init__(self):
        self.frames = []

    def on_input(self, input_):
        self.frames.append(input_)

    def get_num_frames(self):
        return len(self.frames)

    def create_random_recall(self, num_frames_to_recall):
        if random.uniform(0.0, 1.0) < args.reverse_recall_probability:
            return self._create_reverse_recall(num_frames_to_recall)
        else:
            return self._create_normal_recall(num_frames_to_recall)

    def _create_normal_recall(self, num_frames_to_recall):
        max_cursor = self.get_num_frames() - num_frames_to_recall
        cursor = int(random.random() * max_cursor)
        time_direction = 1
        print "normal recall from %s" % cursor
        return Recall(cursor, time_direction)

    def _create_reverse_recall(self, num_frames_to_recall):
        max_cursor = self.get_num_frames() - num_frames_to_recall
        cursor = int(random.random() * max_cursor) + num_frames_to_recall
        time_direction = -1
        print "reverse recall from %s" % cursor
        return Recall(cursor, time_direction)

class Recall:
    def __init__(self, cursor, time_direction):
        self._cursor = cursor
        self._time_direction = time_direction
        
    def proceed(self, num_frames):
        self._cursor += num_frames * self._time_direction

    def get_output(self):
        return memory.frames[self._cursor]

class SwitchingBehavior(Behavior):
    MIRROR = "mirror"
    IMPROVISE = "improvise"
    RECALL = "recall"
    MODES = [MIRROR, IMPROVISE, RECALL]
    
    interpolation_duration = 1.0
    
    def __init__(self):
        self._modes_enabled = {
            mode: self._mode_enabled_in_args(mode) > 0
            for mode in self.MODES}
        self._input = None
        self._delayed_input = None
        self._output = None
        self._mirror_num_frames = int(round(args.mirror_duration * args.frame_rate))
        self._improvise_num_frames = int(round(args.improvise_duration * args.frame_rate))
        self._recall_num_frames = int(round(args.recall_duration * args.frame_rate))
        self._interpolation_num_frames = int(round(self.interpolation_duration * args.frame_rate))
        self._recall_num_frames_including_interpolation = self._recall_num_frames + \
                                                          2 * self._interpolation_num_frames
        initial_state = self._choose_initial_state()
        self._prepare_state(initial_state)
        self._initialize_state(initial_state)
        self._input_buffer_num_frames = int(MAX_DELAY_SECONDS * args.frame_rate)
        self._input_buffer = collections.deque(
            [None] * self._input_buffer_num_frames, maxlen=self._input_buffer_num_frames)
        self.set_mirror_delay_seconds(0)
        self._chainer = Chainer()
        self._delay_shift = SmoothedDelayShift(
            smoothing=10, period_duration=5, peak_duration=3, magnitude=1.5)
        self.set_delay_shift_amount(args.delay_shift)
        self.memorize = False

    def set_delay_shift_amount(self, amount):
        self._delay_shift_amount = amount
    
    def _mode_enabled_in_args(self, mode):
        enabled_arg = "enable_%s" % mode
        return getattr(args, enabled_arg)
        
    def set_mode_enabled(self, mode, enabled):
        self._modes_enabled[mode] = enabled
        
    def set_model(self, model_name):
        self._improvise = improvise_behaviors[model_name]

    def _choose_initial_state(self):
        enabled_modes = [
            mode for mode in self.MODES
            if self._modes_enabled[mode]]
        if len(enabled_modes) == 0:
            raise Exception("at least one mode must be enabled")
        return enabled_modes[0]
        
    def set_mirror_delay_seconds(self, seconds):
        self._input_buffer_read_cursor = self._input_buffer_num_frames - 1 - int(seconds * args.frame_rate)

    def _select_next_state(self):
        other_modes = set(self.MODES) - set([self._current_state])
        available_other_modes = [
            mode for mode in other_modes
            if self._mode_is_available(mode)]
        if len(available_other_modes) == 0:
            print "no other mode available"
            return self._current_state
        else:
            print "available modes:", available_other_modes
            weights = [self._get_weight(mode) for mode in available_other_modes]
            shuffler = WeightedShuffler(available_other_modes, weights)
            return shuffler.choice()

    def _mode_is_available(self, mode):
        if mode == self.RECALL:
            return self._modes_enabled[self.RECALL] and \
                memory.get_num_frames() >= self._recall_num_frames_including_interpolation
        return self._modes_enabled[mode] > 0

    def _get_weight(self, mode):
        weight_arg = "%s_weight" % mode
        return getattr(args, weight_arg)
    
    def _initialize_state(self, state):
        print "initializing %s" % state
        self._current_state = state
        self._state_frames = 0
        self._interpolating = False
        if state == self.RECALL:
            self._current_recall = self._next_recall
            
    def proceed(self, time_increment):
        delay_seconds = self._delay_shift.get_value() * self._delay_shift_amount
        self.set_mirror_delay_seconds(delay_seconds)
        self._delay_shift.proceed(time_increment)
        
        self._delayed_input = self._get_delayed_input()
        if self._delayed_input is None:
            return
        self._remaining_frames_to_process = int(round(time_increment * args.frame_rate))
        while self._remaining_frames_to_process > 0:
            self._proceed_within_state()

    def _proceed_within_state(self):
        if self._interpolating:
            return self._proceed_within_interpolation()
        else:
            return self._proceed_within_normal_state()
        
    def _proceed_within_interpolation(self):
        remaining_frames_in_state = self._interpolation_num_frames - self._state_frames
        if remaining_frames_in_state == 0:
            self._initialize_state(self._next_state)
            return
                
        frames_to_process = min(self._remaining_frames_to_process, remaining_frames_in_state)
        self._improvise.proceed(float(frames_to_process) / args.frame_rate)

        if self._current_state == self.RECALL:
            self._current_recall.proceed(frames_to_process)
        if self._next_state == self.RECALL:
            self._next_recall.proceed(frames_to_process)
            
        from_output = self._state_output(self._current_state, "current")
        to_output = self._state_output(self._next_state, "next")
        amount = float(self._state_frames) / self._interpolation_num_frames
        
        if amount > 0.5 and not self._interpolation_crossed_halfway:
            self._chainer.switch_source()
            self._interpolation_crossed_halfway = True            

        if self._current_state == self.IMPROVISE:
            switching_behavior_entity.set_friction(amount <= 0.5)
        elif self._next_state == self.IMPROVISE:
            switching_behavior_entity.set_friction(amount > 0.5)
        else:
            switching_behavior_entity.set_friction(False)

        if self._interpolation_crossed_halfway:
            translation = self._get_translation(to_output)
        else:
            translation = self._get_translation(from_output)
        self._chainer.put(translation)
        translation = self._chainer.get()
        orientations = self._get_orientations(switching_behavior_entity.interpolate(from_output, to_output, amount))
        self._output = self._combine_translation_and_orientation(translation, orientations)

        self._state_frames += frames_to_process
        self._remaining_frames_to_process -= frames_to_process
    
    def _get_delayed_input(self):
        return self._input_buffer[self._input_buffer_read_cursor]
            
    def _proceed_within_normal_state(self):        
        remaining_frames_in_state = self._state_num_frames(self._current_state) - self._state_frames
        if remaining_frames_in_state == 0:
            self._interpolating = True
            self._interpolation_crossed_halfway = False
            self._state_frames = 0
            self._next_state = self._select_next_state()
            print "%s => %s" % (self._current_state, self._next_state)
            self._prepare_state(self._next_state)
            return
        frames_to_process = min(self._remaining_frames_to_process, remaining_frames_in_state)
        self._improvise.proceed(float(frames_to_process) / args.frame_rate)

        if self._current_state == self.RECALL:
            self._current_recall.proceed(frames_to_process)
            
        output = self._state_output(self._current_state, "current")
        if self._current_state == self.IMPROVISE:
            switching_behavior_entity.set_friction(True)
        elif self._current_state == self.MIRROR:
            switching_behavior_entity.set_friction(False)
        elif self._current_state == self.RECALL:
            switching_behavior_entity.set_friction(False)

        translation = self._get_translation(output)
        orientations = self._get_orientations(output)
        self._chainer.put(translation)
        translation = self._chainer.get()
        self._output = self._combine_translation_and_orientation(translation, orientations)
            
        self._state_frames += frames_to_process
        self._remaining_frames_to_process -= frames_to_process

    def _state_output(self, state, current_or_next):
        if state == self.IMPROVISE:
            return self._get_improvise_output()
        elif state == self.MIRROR:
            return self._delayed_input
        elif state == self.RECALL:
            if current_or_next == "current":
                return self._current_recall.get_output()
            elif current_or_next == "next":
                return self._next_recall.get_output()
            else:
                raise Exception("expected current or next but got %r" % current_or_next)
        else:
            raise Exception("unknown state %r" % state)
            
    def _prepare_state(self, state):
        print "preparing %s" % state
        if state == self.RECALL:
            self._next_recall = memory.create_random_recall(
                self._recall_num_frames_including_interpolation)

    def _state_num_frames(self, state):
        if state == self.MIRROR:
            return self._mirror_num_frames
        elif state == self.IMPROVISE:
            return self._improvise_num_frames
        elif state == self.RECALL:
            return self._recall_num_frames
        
    def sends_output(self):
        return True

    def on_input(self, input_):
        self._input = input_
        self._input_buffer.append(input_)
        if self.memorize:
            memory.on_input(input_)
        
    def get_output(self):
        return self._output

    def _get_improvise_output(self):
        reduction = self._improvise.get_reduction()
        return student.inverse_transform(numpy.array([reduction]))[0]

    def _get_translation(self, parameters):
        return parameters[0:3]

    def _get_orientations(self, parameters):
        return parameters[3:]

    def _combine_translation_and_orientation(self, translation, orientations):
        return numpy.array(list(translation) + list(orientations))
    
class UiWindow(BaseUiWindow):
    def __init__(self, master_behavior):
        super(UiWindow, self).__init__(application, master_behavior)
        self._add_learning_rate_control()
        self._add_memorize_control()
        self._add_io_blending_control()
        self._add_model_control()
        self._add_mode_controls()
        self._add_delay_shift_control()

    def _add_learning_rate_control(self):
        self._control_layout.add_label("Learning rate")
        self._learning_rate_slider = self._create_learning_rate_slider()
        self._control_layout.add_control_widget(self._learning_rate_slider)
        
    def _create_learning_rate_slider(self):
        slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, SLIDER_PRECISION)
        slider.setSingleStep(1)
        slider.setValue(args.learning_rate / MAX_LEARNING_RATE * SLIDER_PRECISION)
        slider.valueChanged.connect(lambda value: self._on_changed_learning_rate_slider())
        return slider

    def _on_changed_learning_rate_slider(self):
        learning_rate = float(self._learning_rate_slider.value()) / SLIDER_PRECISION * MAX_LEARNING_RATE
        students["autoencoder"].set_learning_rate(learning_rate)

    def _add_memorize_control(self):
        self._control_layout.add_label("Memorize")
        self._memorize_checkbox = QtGui.QCheckBox()
        self._memorize_checkbox.stateChanged.connect(self._on_changed_memorize)
        self._control_layout.add_control_widget(self._memorize_checkbox)

    def _on_changed_memorize(self):
        switching_behavior.memorize = self._memorize_checkbox.isChecked()
        
    def _mode_enabled_in_args(self, mode):
        enabled_arg = "enable_%s" % mode
        return getattr(args, enabled_arg)

    def _mode_checkbox_changed(self, mode, checkbox):
        switching_behavior.set_mode_enabled(mode, checkbox.isChecked())

    def _add_io_blending_control(self):
        self._control_layout.add_label("IO blending")
        self._io_blending_slider = self._create_io_blending_slider()
        self._control_layout.add_control_widget(self._io_blending_slider)
        self._on_changed_io_blending_slider()

    def _add_label(self, string):
        label = QtGui.QLabel(string)
        self._layout.addWidget(label, self._row, 0)

    def _add_control_widget(self, widget):
        self._layout.addWidget(widget, self._row, 1)
        self._row += 1
        
    def _create_io_blending_slider(self):
        slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, SLIDER_PRECISION)
        slider.setSingleStep(1)
        slider.setValue(args.io_blending_amount * SLIDER_PRECISION)
        slider.valueChanged.connect(lambda value: self._on_changed_io_blending_slider())
        return slider

    def _on_changed_io_blending_slider(self):
        io_blending_amount = float(self._io_blending_slider.value()) / SLIDER_PRECISION
        self._master_behavior.set_io_blending_amount(io_blending_amount)

    def _add_model_control(self):
        model_combobox = self._create_model_combobox()
        self._control_layout.add_label("Model")
        self._control_layout.add_control_widget(model_combobox)
        
    def _create_model_combobox(self):
        combobox = QtGui.QComboBox()
        for model_name in MODELS:
            combobox.addItem(model_name)
        combobox.activated.connect(self._changed_model)
        combobox.setCurrentIndex(combobox.findText(args.model))
        return combobox

    def _changed_model(self, value):
        set_model(MODELS[value])

    def _add_mode_controls(self):
        self._add_mode_control("Mirror", SwitchingBehavior.MIRROR)
        self._add_mode_control("Recall", SwitchingBehavior.RECALL)
        self._add_mode_control("Improvise", SwitchingBehavior.IMPROVISE)

    def _add_mode_control(self, name, mode):
        self._control_layout.add_label(name)
        self._control_layout.add_control_widget(self._create_mode_checkbox(mode))

    def _create_mode_checkbox(self, mode):
        checkbox = QtGui.QCheckBox()
        checkbox.setChecked(self._mode_enabled_in_args(mode) > 0)
        checkbox.stateChanged.connect(lambda event: self._mode_checkbox_changed(mode, checkbox))
        return checkbox
    
    def _mode_enabled_in_args(self, mode):
        enabled_arg = "enable_%s" % mode
        return getattr(args, enabled_arg)

    def _mode_checkbox_changed(self, mode, checkbox):
        switching_behavior.set_mode_enabled(mode, checkbox.isChecked())

    def _add_delay_shift_control(self):
        self._control_layout.add_label("Delay shift")
        self._delay_shift_slider = self._create_delay_shift_slider()
        self._control_layout.add_control_widget(self._delay_shift_slider)
        
    def _create_delay_shift_slider(self):
        slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, SLIDER_PRECISION)
        slider.setSingleStep(1)
        slider.setValue(args.delay_shift * SLIDER_PRECISION)
        slider.valueChanged.connect(lambda value: self._on_changed_delay_shift_slider())
        return slider

    def _on_changed_delay_shift_slider(self):
        delay_shift_amount = float(self._delay_shift_slider.value()) / SLIDER_PRECISION
        switching_behavior.set_delay_shift_amount(delay_shift_amount)
        
        
class MasterBehavior(Behavior):
    def __init__(self):
        Behavior.__init__(self)
        self._io_blending_amount = args.io_blending_amount
        self._input = None

    def set_model(self, model_name):
        switching_behavior.set_model(model_name)

    def proceed(self, time_increment):
        switching_behavior.proceed(time_increment)
        if self._io_blending_amount < 0.5:
            master_entity.set_friction(True)
        else:
            master_entity.set_friction(switching_behavior_entity.get_friction())
        
    def sends_output(self):
        return True
    
    def get_output(self):
        switching_behavior_output = switching_behavior.get_output()
        if self._input is None or switching_behavior_output is None:
            return None
        return master_entity.interpolate(self._input, switching_behavior_output, self._io_blending_amount)

    def on_input(self, input_):
        self._input = input_
        switching_behavior.on_input(input_)

    def set_io_blending_amount(self, amount):
        self._io_blending_amount = amount

def _create_improvise_behavior(model_name):
    improvise_params = ImproviseParameters()
    preferred_location = None
    student = students[model_name]
    return Improvise(
        student,
        student.num_reduced_dimensions,
        improvise_params,
        preferred_location,
        MAX_NOVELTY)

improvise_behaviors = {
    model_name: _create_improvise_behavior(model_name)
    for model_name in MODELS}

index = 0
memory = Memory()
switching_behavior = SwitchingBehavior()
master_behavior = MasterBehavior()
avatar = Avatar(index, master_entity, master_behavior)

avatars = [avatar]

application = Application(students[args.model], avatars, args)

set_model(args.model)

def receive_from_pn(pn_entity):
    for frame in pn_receiver.get_frames():
        input_from_pn = pn_entity.get_value_from_frame(frame, convert_to_z_up=args.pn_convert_to_z_up)
        input_from_pn[0:3] += pn_translation_offset
        application.set_input(input_from_pn)
        
pn_receiver = tracking.pn.receiver.PnReceiver()
print "connecting to PN server..."
pn_receiver.connect(args.pn_host, args.pn_port)
print "ok"
pn_entity = create_entity()
if args.pn_translation_offset:
    pn_translation_offset = numpy.array(
        [float(string) for string in args.pn_translation_offset.split(",")])
else:
    pn_translation_offset = numpy.array([0,0,0])
pn_receiver_thread = threading.Thread(target=lambda: receive_from_pn(pn_entity))
pn_receiver_thread.daemon = True
pn_receiver_thread.start()

if args.with_ui:
    qt_app = QtGui.QApplication(sys.argv)
    ui_window = UiWindow(master_behavior)
    ui_window.show()
    qt_app.exec_()
else:
    application.run()
