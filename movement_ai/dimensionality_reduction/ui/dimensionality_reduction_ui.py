from ..dimensionality_reduction_experiment import *
from ui.ui import *
from reduction_tab import ReductionTab
from map_widget import MapTab
from reduction_sliders import ReductionSliders
from .. import modes
from feature_sliders import FeatureSliders
import math

REDUCTION_PLOT_PATH = "reduction.dat"
HTML5_TOOLBAR_HEIGHT = 250

class DimensionalityReductionMainWindow(MainWindow):
    @staticmethod
    def add_parser_arguments(parser):
        MainWindow.add_parser_arguments(parser)
        parser.add_argument("--html5-toolbar", action="store_true")

    def __init__(self, *args, **kwargs):
        MainWindow.__init__(self, *args, event_handlers={
            Event.REDUCTION: self._handle_reduction,
            Event.MODE: self._set_mode,
            Event.CURSOR: self._set_cursor,
            Event.BVH_INDEX: self._update_bvh_selector,
            Event.PARAMETER: self._received_parameter,
            Event.FEATURES: self._handle_features,
            Event.TARGET_FEATURES: self._handle_target_features,
            Event.FEATURE_MATCH_OUTPUT: self._handle_feature_match_output,
            Event.TARGET_ROOT_VERTICAL_ORIENTATION: self._handle_target_root_vertical_orientation,
            Event.REDUCTION_RANGE: self._handle_reduction_range,
            Event.NORMALIZED_OBSERVED_REDUCTIONS: self._handle_normalized_observed_reductions,
            Event.IO_BLENDING_AMOUNT: self._set_io_blending_amount,
            Event.TRAINING_LOSS: self._handle_training_loss,
        }, **kwargs)
        self._add_toggleable_action(
            '&Plot reduction', self._start_plot_reduction,
            '&Stop plot', self._stop_plot_reduction,
            False, 'F1')
        self._reduction_plot = None
        self._add_show_reduction_action()
        self._create_improvisation_menu()
        if self.args.html5_toolbar:
            self._add_html5_toolbar()

    def _received_parameter(self, event):
        self.toolbar.received_parameter(event)

    def _add_show_reduction_action(self):
        action = QtGui.QAction('Show normalized reduction', self)
        action.triggered.connect(self._show_normalized_reduction)
        self._main_menu.addAction(action)

    def _create_improvisation_menu(self):
        self._improvisation_menu = self._menu_bar.addMenu("Improvisation")
        self._add_abort_path_action()

    def _add_abort_path_action(self):
        action = QtGui.QAction('Abort path', self)
        action.setShortcut('F12')
        action.triggered.connect(lambda: self.send_event(Event(Event.ABORT_PATH)))
        self._improvisation_menu.addAction(action)

    def _show_normalized_reduction(self):
        normalized_reduction = self.student.normalize_reduction(self.reduction)
        print ",".join([str(v) for v in normalized_reduction])

    def _add_html5_toolbar(self):
        from PyQt4.QtCore import QUrl
        from PyQt4.QtWebKit import QWebView, QWebSettings
        view = QWebView()
        view.load(QUrl("dimensionality_reduction/html5/index.html?stylesheet=ui_720p"))
        view.show()
        view.setFixedSize(self.args.preferred_width, HTML5_TOOLBAR_HEIGHT)
        self.setFixedSize(self.args.preferred_width, self.args.preferred_height)
        self.outer_vertical_layout.addWidget(view)
        view.page().settings().setAttribute(QWebSettings.DeveloperExtrasEnabled, True)

    def _handle_reduction(self, event):
        self.reduction = event.content
        if self._reduction_plot:
            print >>self._reduction_plot, " ".join([
                    str(v) for v in self.student.normalize_reduction(self.reduction)])
        self.toolbar.on_received_reduction_from_backend(self.reduction)

    def _start_plot_reduction(self):
        self._reduction_plot = open(REDUCTION_PLOT_PATH, "w")
        print "plotting reduction"

    def _stop_plot_reduction(self):
        self._reduction_plot.close()
        self._reduction_plot = None
        print "saved reduction data to %s" % REDUCTION_PLOT_PATH

    def _set_mode(self, event):
        mode = event.content
        self.toolbar.set_mode(mode)

    def _set_cursor(self, event):
        if hasattr(self.toolbar, "cursor_slider"):
            self.toolbar.cursor_slider.setValue(event.content * SLIDER_PRECISION)

    def _update_bvh_selector(self, event):
        self.toolbar.bvh_selector.setCurrentIndex(event.content)

    def update_qgl_widgets(self):
        MainWindow.update_qgl_widgets(self)
        self.toolbar.update_qgl_widgets()

    def _handle_features(self, event):
        self.toolbar.on_received_features_from_backend(event)

    def _handle_target_features(self, event):
        self.toolbar.on_received_target_features_from_backend(event)

    def _handle_feature_match_output(self, event):
        feature_match_tuples = event.content
        feature_match_tuples_sorted_by_distance = sorted(
            feature_match_tuples,
            key=lambda feature_match_tuple: -feature_match_tuple[1])
        feature_match_result_with_opacity = []
        n = 0
        for processed_output, _ in feature_match_tuples_sorted_by_distance:
            if len(feature_match_tuples) == 1:
                opacity = 1
            else:
                opacity = float(n) / (len(feature_match_tuples)-1)
            feature_match_result_with_opacity.append((processed_output, opacity))
            n += 1
        self._scene.feature_match_result = feature_match_result_with_opacity

    def _handle_target_root_vertical_orientation(self, event):
        self.toolbar.handle_target_root_vertical_orientation(event.content)

    def get_root_vertical_orientation(self):
        return self.toolbar.get_root_vertical_orientation()

    def _handle_reduction_range(self, event):
        self.toolbar.set_reduction_range(event.content)

    def _handle_normalized_observed_reductions(self, event):
        self.toolbar.set_normalized_observed_reductions(event.content)

    def _set_io_blending_amount(self, event):
        self.toolbar.io_blending_slider.setValue(event.content * SLIDER_PRECISION)

    def _handle_training_loss(self, event):
        self.toolbar.training_loss_value.setText("%.2f" % event.content)

class DimensionalityReductionToolbar(ExperimentToolbar):
    def __init__(self, *args):
        ExperimentToolbar.__init__(self, *args)
        self.set_reduction_range(self.parent().student.reduction_range)
        self._layout = QtGui.QHBoxLayout()
        self.add_input_tab_widget(self._layout)
        self._add_mode_tabs()
        self._add_reduction_tabs()
        if self.args.enable_io_blending:
            self._add_io_blending_tab_widget()
        if self.args.enable_features:
            self._add_features_tab_widgets()
        self.add_entity_tab_widget(self._layout)
        self.add_learning_tab_widget(self._layout)
        self.setLayout(self._layout)
        self.set_mode(self.args.mode)
        self._activate_current_mode()

    def set_reduction_range(self, reduction_range):
        self.reduction_range = reduction_range
        self._set_exploration_ranges()
        
    def _set_exploration_ranges(self):
        for n in range(self.parent().student.num_reduced_dimensions):
            self._set_exploration_range(self.reduction_range[n])

    def _set_exploration_range(self, reduction_range):
        reduction_range["explored_range"] = (1.0 + self.parent().args.explore_beyond_observations)
        reduction_range["explored_min"] = .5 - reduction_range["explored_range"]/2
        reduction_range["explored_max"] = .5 + reduction_range["explored_range"]/2

    def set_normalized_observed_reductions(self, normalized_observed_reductions):
        self.map_tab.set_normalized_observed_reductions(normalized_observed_reductions)

    def get_event_handlers(self):
        if self.map_tab:
            return self.map_tab.get_event_handlers()
        else:
            return {}

    def set_mode(self, mode):
        self._mode = mode
        mode_tab = self._mode_tabs[mode]
        self._changing_mode_non_interactively = True
        self.tabs.setCurrentWidget(mode_tab)
        self._changing_mode_non_interactively = False

    def get_mode(self):
        return self._mode

    def _add_mode_tabs(self):
        self._parameter_sets = {}
        self.tabs = QtGui.QTabWidget()
        self._mode_tabs = {}
        self._add_memory_tab()
        if self.args.mode == modes.FOLLOW:
            self._add_follow_tab()
        self._add_explore_tab()
        self._add_improvise_tab()
        self._add_flaneur_tab()
        if self.args.enable_features:
            self._add_imitate_tab()
            self._add_hybrid_tab()
        self.tabs.currentChanged.connect(self._changed_mode_tab)
        self._layout.addWidget(self.tabs)
        self._changing_mode_non_interactively = False

    def _changed_mode_tab(self):
        self._mode = self.tabs.currentWidget()._mode_id
        self._activate_current_mode()
        if not self._changing_mode_non_interactively:
            self.parent().send_event(Event(Event.MODE, self._mode))

    def _activate_current_mode(self):
        exploring = (self._mode == modes.EXPLORE)
        for n in range(self._reduction_tabs.count()):
            tab = self._reduction_tabs.widget(n)
            tab.set_enabled(exploring)

    def _add_memory_tab(self):
        self.memory_tab = ModeTab(modes.MEMORY)
        self._memory_tab_layout = QtGui.QVBoxLayout()
        memorize_checkbox_layout = self._add_memorize_checkbox_layout()
        self._memory_tab_layout.addLayout(memorize_checkbox_layout)
        self._add_recall_button()
        self._memory_tab_layout.addStretch(1)
        self.memory_tab.setLayout(self._memory_tab_layout)
        self.tabs.addTab(self.memory_tab, "Memory")
        self._mode_tabs[modes.MEMORY] = self.memory_tab

    def _add_memorize_checkbox_layout(self):
        layout = QtGui.QHBoxLayout()
        layout.setMargin(5)
        self._memorize_checkbox = QtGui.QCheckBox()
        self._memorize_checkbox.setChecked(self.parent().split_output_and_io_blend)
        self._memorize_checkbox.stateChanged.connect(self._memorize_checkbox_changed)
        label = QtGui.QLabel("Memorize")
        layout.addWidget(self._memorize_checkbox)
        layout.addWidget(label)
        layout.addStretch(1)
        return layout

    def _memorize_checkbox_changed(self, event):
        self.parent().client.send_event(Event(Event.SET_MEMORIZE, self._memorize_checkbox.isChecked()))
        
    def _add_recall_button(self):
        button = QtGui.QPushButton("Recall", self)
        button.clicked.connect(self._recall)
        self._memory_tab_layout.addWidget(button)

    def _recall(self):
        self.parent().client.send_event(Event(Event.RECALL))
        
    def _add_follow_tab(self):
        self.follow_tab = ModeTab(modes.FOLLOW)
        if not self.args.receive_from_pn:
            self._follow_tab_layout = QtGui.QVBoxLayout()
            if hasattr(self.parent().entity, "get_duration"):
                self._add_cursor_slider()
            if self.args.bvh:
                self._add_bvh_selector()
            self._follow_tab_layout.addStretch(1)
            self.follow_tab.setLayout(self._follow_tab_layout)
        self.tabs.addTab(self.follow_tab, "Follow")
        self._mode_tabs[modes.FOLLOW] = self.follow_tab

    def _add_cursor_slider(self):
        self.cursor_slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.cursor_slider.setRange(0, SLIDER_PRECISION)
        self.cursor_slider.setSingleStep(1)
        self.cursor_slider.setValue(0.0)
        self.cursor_slider.valueChanged.connect(self._cursor_changed)
        self._follow_tab_layout.addWidget(self.cursor_slider)

    def _add_bvh_selector(self):
        self.bvh_selector = QtGui.QComboBox()
        for bvh_reader in self.parent().entity.bvh_reader.get_readers():
            self.bvh_selector.addItem(bvh_reader.filename)
        self._follow_tab_layout.addWidget(self.bvh_selector)

    def _cursor_changed(self, value):
        self.parent().send_event(Event(
                Event.SET_CURSOR,
                float(value) / SLIDER_PRECISION * self.parent().entity.get_duration()))

    def _add_explore_tab(self):
        self.explore_tab = ModeTab(modes.EXPLORE)
        self._explore_tab_layout = QtGui.QVBoxLayout()
        self._add_random_button()
        self._add_deviate_button()
        if self.parent().args.entity == "hierarchical":
            self._add_root_vertical_orientation_form()
        self._explore_tab_layout.addStretch(1)
        self.explore_tab.setLayout(self._explore_tab_layout)
        self.tabs.addTab(self.explore_tab, "Explore")
        self._mode_tabs[modes.EXPLORE] = self.explore_tab

    def _add_random_button(self):
        button = QtGui.QPushButton("Random", self)
        button.clicked.connect(self._set_random_reduction)
        self._explore_tab_layout.addWidget(button)

    def _add_deviate_button(self):
        layout = QtGui.QHBoxLayout()
        self.deviation_slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.deviation_slider.setRange(0, SLIDER_PRECISION)
        self.deviation_slider.setSingleStep(1)
        self.deviation_slider.setValue(0.0)
        layout.addWidget(self.deviation_slider)
        button = QtGui.QPushButton("Deviate", self)
        button.clicked.connect(self._set_deviated_reduction)
        layout.addWidget(button)
        self._explore_tab_layout.addLayout(layout)

    def _add_root_vertical_orientation_form(self):
        class OrientationSlider(QtGui.QDial):
            def __init__(self):
                QtGui.QDial.__init__(self)
                self.setWrapping(True)
                self.setRange(0, SLIDER_PRECISION)
                self.setSingleStep(1)
                self.setValue(0.0)

            def sizeHint(self):
                return QtCore.QSize(50, 50)

        layout = QtGui.QHBoxLayout()
        self._root_vertical_orientation_checkbox = QtGui.QCheckBox()
        self._root_vertical_orientation_checkbox.stateChanged.connect(
            self._root_vertical_orientation_checkbox_changed)
        layout.addWidget(self._root_vertical_orientation_checkbox)
        label = QtGui.QLabel("Lock vertical orientation")
        layout.addWidget(label)
        self._root_vertical_orientation_slider = OrientationSlider()
        self._root_vertical_orientation_slider.valueChanged.connect(
            self._root_vertical_orientation_changed)
        self._root_vertical_orientation_slider.setEnabled(False)
        layout.addWidget(self._root_vertical_orientation_slider)
        layout.addStretch(1)
        self._explore_tab_layout.addLayout(layout)

    def _root_vertical_orientation_checkbox_changed(self, event):
        self._root_vertical_orientation_slider.setEnabled(
            self._root_vertical_orientation_checkbox.isChecked())
        self._send_root_orientation()

    def _send_root_orientation(self):
        self.parent().client.send_event(
            Event(Event.TARGET_ROOT_VERTICAL_ORIENTATION, self.get_root_vertical_orientation()))

    def get_root_vertical_orientation(self):
        if self._root_vertical_orientation_checkbox.checkState() == QtCore.Qt.Checked:
            return float(
                self._root_vertical_orientation_slider.value()) / SLIDER_PRECISION * math.pi*2
        else:
            return None

    def _root_vertical_orientation_changed(self, event):
        self._send_root_orientation()

    def handle_target_root_vertical_orientation(self, unclamped_y_orientation):
        clamped_y_orientation = unclamped_y_orientation % (math.pi*2)
        self._root_vertical_orientation_slider.setValue(
            int(clamped_y_orientation * SLIDER_PRECISION / (math.pi*2)))

    def _add_imitate_tab(self):
        self.imitate_tab = ModeTab(modes.IMITATE)
        self._imitate_tab_layout = QtGui.QVBoxLayout()
        self._imitate_params = ImitateParameters()
        self._imitate_params.add_listener(self._send_changed_parameter)
        self._imitate_params_form = self.add_parameter_fields(
            self._imitate_params, self._imitate_tab_layout)
        self._add_parameter_set(self._imitate_params, self._imitate_params_form)
        self._imitate_tab_layout.addStretch(1)
        self.imitate_tab.setLayout(self._imitate_tab_layout)
        self.tabs.addTab(self.imitate_tab, "Imitate")
        self._mode_tabs[modes.IMITATE] = self.imitate_tab

    def _add_hybrid_tab(self):
        self.hybrid_tab = ModeTab(modes.HYBRID)
        self._hybrid_tab_layout = QtGui.QVBoxLayout()
        self._hybrid_params = HybridParameters()
        self._hybrid_params.add_listener(self._send_changed_parameter)
        self._hybrid_params_form = self.add_parameter_fields(
            self._hybrid_params, self._hybrid_tab_layout)
        self._add_parameter_set(self._hybrid_params, self._hybrid_params_form)
        self._hybrid_tab_layout.addStretch(1)
        self.hybrid_tab.setLayout(self._hybrid_tab_layout)
        self.tabs.addTab(self.hybrid_tab, "Hybrid")
        self._mode_tabs[modes.HYBRID] = self.hybrid_tab

    def _add_improvise_tab(self):
        self.improvise_tab = ModeTab(modes.IMPROVISE)
        self._improvise_tab_layout = QtGui.QVBoxLayout()
        self._improvise_params = ImproviseParameters()
        self._improvise_params.add_listener(self._send_changed_parameter)
        self._improvise_params_form = self.add_parameter_fields(
            self._improvise_params, self._improvise_tab_layout)
        self._improvise_tab_layout.addStretch(1)
        self.improvise_tab.setLayout(self._improvise_tab_layout)
        self.tabs.addTab(self.improvise_tab, "Improvise")
        self._mode_tabs[modes.IMPROVISE] = self.improvise_tab
        self._add_parameter_set(self._improvise_params, self._improvise_params_form)

    def _send_changed_parameter(self, parameter):
        self.parent().client.send_event(Event(
                Event.PARAMETER,
                {"class": parameter.parameters.__class__.__name__,
                 "name": parameter.name,
                 "value": parameter.value()}))

    def received_parameter(self, event):
        class_name = event.content["class"]
        parameter_set = self._parameter_sets[class_name]
        parameters = parameter_set["parameters"]
        parameter_name = event.content["name"]
        parameter = parameters.get_parameter(parameter_name)
        parameter.set_value(event.content["value"], notify=False)
        parameter_set["form"].update_field_to_reflect_changed_value(parameter)

    def get_num_reduced_dimensions(self):
        return self.parent().student.num_reduced_dimensions
    
    def _add_reduction_tabs(self):
        self._reduction_tabs = QtGui.QTabWidget()
        if self.parent().student.num_reduced_dimensions >= 2:
            self._add_map_tab()
        else:
            self.map_tab = None
        self._add_reduction_sliders_tab()
        self._layout.addWidget(self._reduction_tabs)

    def _add_reduction_sliders_tab(self):
        self.reduction_sliders_tab = ReductionSliders(self)
        self._reduction_tabs.addTab(self.reduction_sliders_tab, "Orthogonal control")

    def _add_map_tab(self):
        self._map_dimensions = [0,1]
        self.map_tab = MapTab(self, self._map_dimensions, self.parent().student.normalized_observed_reductions)
        self._reduction_tabs.addTab(self.map_tab, "2D map")

    def _set_random_reduction(self):
        for n in range(self.parent().student.num_reduced_dimensions):
            self._set_random_reduction_n(
                n, self.reduction_range[n])

    def _set_random_reduction_n(self, n, reduction_range):
        self.reduction_sliders_tab.slider(n).setValue(
            self._normalized_reduction_value_to_slider_value(
                n, random.uniform(reduction_range["explored_min"],
                                  reduction_range["explored_max"])))

    def _set_deviated_reduction(self):
        random_observation = self.parent().entity.get_random_value()
        undeviated_reduction = self.parent().student.transform(numpy.array([
                    random_observation]))[0]
        deviated_reduction = undeviated_reduction + self._random_deviation()
        self._set_reduction(deviated_reduction)

    def _random_deviation(self):
        return [self._random_deviation_n(n)
                for n in range(self.parent().student.num_reduced_dimensions)]
    
    def _random_deviation_n(self, n):
        reduction_range = self.reduction_range[n]
        max_deviation = float(self.deviation_slider.value()) / SLIDER_PRECISION \
            * (reduction_range["max"] - reduction_range["min"])
        return random.uniform(-max_deviation, max_deviation)

    def _set_reduction(self, reduction):
        normalized_reduction = self.parent().student.normalize_reduction(reduction)
        self._update_current_reduction_widget(normalized_reduction)

    def _update_current_reduction_widget(self, normalized_reduction):
        self._reduction_tabs.currentWidget().reduction_changed(normalized_reduction)

    def refresh(self):
        if self._mode != modes.EXPLORE:
            normalized_reduction = self.parent().student.normalize_reduction(
                self.parent().reduction)
            self._update_current_reduction_widget(normalized_reduction)

    def reduction_changed_interactively(self, source_tab):
        normalized_reduction = source_tab.get_normalized_reduction()
        reduction = self.parent().student.unnormalize_reduction(normalized_reduction)
        self.parent().send_event(Event(Event.REDUCTION, reduction))
        self.parent().reduction = reduction
        for n in range(self._reduction_tabs.count()):
            tab = self._reduction_tabs.widget(n)
            if tab != source_tab:
                tab.reduction_changed(normalized_reduction)

    def get_reduction(self):
        return self.parent().student.unnormalize_reduction(
            self._reduction_tabs.currentWidget().get_normalized_reduction())

    def on_received_reduction_from_backend(self, reduction):
        self._set_reduction(reduction)

    def update_qgl_widgets(self):
        self._reduction_tabs.currentWidget().update_qgl_widgets()

    def _add_io_blending_tab_widget(self):
        io_blending_tab_widget = QtGui.QTabWidget()
        io_blending_tab = QtGui.QWidget()
        layout = QtGui.QVBoxLayout()
        layout.setSpacing(0)
        layout.setMargin(0)
        io_blending_tab.setLayout(layout)
        self.io_blending_slider = self._create_io_blending_slider()
        layout.addWidget(self.io_blending_slider)
        use_entity_specific_interpolation_layout = self._create_io_blending_use_entity_specific_interpolation_checkbox_layout()
        layout.addLayout(use_entity_specific_interpolation_layout)
        split_output_and_io_blend_layout = self._create_split_output_and_io_blend_checkbox_layout()
        layout.addLayout(split_output_and_io_blend_layout)
        control_friction_layout = self._create_control_friction_checkbox_layout()
        layout.addLayout(control_friction_layout)
        layout.addStretch(1)
        io_blending_tab_widget.addTab(io_blending_tab, "Blending")
        self._layout.addWidget(io_blending_tab_widget)

    def _create_io_blending_slider(self):
        slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, SLIDER_PRECISION)
        slider.setSingleStep(1)
        slider.setValue(0.0)
        slider.valueChanged.connect(self._io_blending_amount_changed_interactively)
        return slider

    def _io_blending_amount_changed_interactively(self, value):
        self.parent().send_event(Event(Event.SET_IO_BLENDING_AMOUNT, float(value) / SLIDER_PRECISION))

    def _create_io_blending_use_entity_specific_interpolation_checkbox_layout(self):
        layout = QtGui.QHBoxLayout()
        layout.setMargin(5)
        self._io_blending_use_entity_specific_interpolation_checkbox = QtGui.QCheckBox()
        self._io_blending_use_entity_specific_interpolation_checkbox.setChecked(True)
        self._io_blending_use_entity_specific_interpolation_checkbox.stateChanged.connect(
            self._io_blending_use_entity_specific_interpolation_checkbox_changed)
        label = QtGui.QLabel("Entity specific interpolation")
        layout.addWidget(self._io_blending_use_entity_specific_interpolation_checkbox)
        layout.addWidget(label)
        layout.addStretch(1)
        return layout

    def _io_blending_use_entity_specific_interpolation_checkbox_changed(self, event):
        self.parent().send_event(Event(Event.SET_IO_BLENDING_USE_ENTITY_SPECIFIC_INTERPOLATION,
                                       self._io_blending_use_entity_specific_interpolation_checkbox.isChecked()))

    def _create_split_output_and_io_blend_checkbox_layout(self):
        layout = QtGui.QHBoxLayout()
        layout.setMargin(5)
        self._split_output_and_io_blend_checkbox = QtGui.QCheckBox()
        self._split_output_and_io_blend_checkbox.setChecked(self.parent().split_output_and_io_blend)
        self._split_output_and_io_blend_checkbox.stateChanged.connect(self._split_output_and_io_blend_checkbox_changed)
        label = QtGui.QLabel("Split output and blend")
        layout.addWidget(self._split_output_and_io_blend_checkbox)
        layout.addWidget(label)
        layout.addStretch(1)
        return layout

    def _split_output_and_io_blend_checkbox_changed(self):
        self.parent().split_output_and_io_blend = self._split_output_and_io_blend_checkbox.isChecked()

    def _create_control_friction_checkbox_layout(self):
        layout = QtGui.QHBoxLayout()
        layout.setMargin(5)
        self._control_friction_checkbox = QtGui.QCheckBox()
        self._control_friction_checkbox.setChecked(True)
        self._control_friction_checkbox.stateChanged.connect(self._control_friction_checkbox_changed)
        label = QtGui.QLabel("Control friction")
        layout.addWidget(self._control_friction_checkbox)
        layout.addWidget(label)
        layout.addStretch(1)
        return layout

    def _control_friction_checkbox_changed(self):
        self.parent().send_event(Event(Event.SET_IO_BLENDING_CONTROL_FRICTION, self._control_friction_checkbox.isChecked()))
        self.enable_friction_checkbox.setEnabled(not self._control_friction_checkbox.isChecked())
        
    def _add_features_tab_widgets(self):
        if self.args.show_output_features:
            self._add_output_features_tab_widget()
        self._add_input_features_tab_widget()

    def _add_output_features_tab_widget(self):
        self._output_features_tab_widget = QtGui.QTabWidget()
        self._output_features_sliders = FeatureSliders(self, self.parent().entity.feature_extractor)
        self._output_features_tab_widget.addTab(self._output_features_sliders, "Output features")
        self._layout.addWidget(self._output_features_tab_widget)

    def _add_input_features_tab_widget(self):
        self._target_features_tab_widget = QtGui.QTabWidget()
        self._target_features_sliders_tab = QtGui.QWidget()
        layout = QtGui.QVBoxLayout()
        layout.setSpacing(0)
        layout.setMargin(0)
        self._target_features_sliders_tab.setLayout(layout)
        self._target_features_sliders = FeatureSliders(self, self.parent().entity.feature_extractor)
        layout.addWidget(self._target_features_sliders)
        layout.addLayout(self._create_target_features_checkbox_layout())
        layout.addStretch(1)
        self._target_features_tab_widget.addTab(self._target_features_sliders_tab, "Target features")
        self._layout.addWidget(self._target_features_tab_widget)

    def _create_target_features_checkbox_layout(self):
        layout = QtGui.QHBoxLayout()
        layout.setMargin(5)
        self._target_features_checkbox = QtGui.QCheckBox()
        self._target_features_checkbox.stateChanged.connect(self._target_features_checkbox_changed)
        label = QtGui.QLabel("Enable target")
        layout.addWidget(self._target_features_checkbox)
        layout.addWidget(label)
        layout.addStretch(1)
        return layout

    def _target_features_checkbox_changed(self):
        enabled = (self._target_features_checkbox.checkState() == QtCore.Qt.Checked)
        self._target_features_sliders.set_enabled(enabled)
        if enabled:
            self.features_changed_interactively()
        else:
            self.parent().send_event(Event(Event.TARGET_FEATURES, None))
            
    def on_received_features_from_backend(self, event):
        features = event.content
        self._output_features_sliders.features_changed(features)
            
    def on_received_target_features_from_backend(self, event):
        features = event.content
        self._target_features_sliders.features_changed(features)

    def features_changed_interactively(self):
        features = self._target_features_sliders.get_features()
        self.parent().send_event(Event(Event.TARGET_FEATURES, features))

    def _add_flaneur_tab(self):
        self.flaneur_tab = ModeTab(modes.FLANEUR)
        self._flaneur_tab_layout = QtGui.QVBoxLayout()
        self._flaneur_params = FlaneurParameters()
        self._flaneur_params.add_listener(self._send_changed_parameter)
        self._flaneur_params_form = self.add_parameter_fields(
            self._flaneur_params, self._flaneur_tab_layout)
        self._add_parameter_set(self._flaneur_params, self._flaneur_params_form)
        self._flaneur_tab_layout.addStretch(1)
        self.flaneur_tab.setLayout(self._flaneur_tab_layout)
        self.tabs.addTab(self.flaneur_tab, "Flaneur")
        self._mode_tabs[modes.FLANEUR] = self.flaneur_tab

    def _add_parameter_set(self, parameters, form):
        self._parameter_sets[parameters.__class__.__name__] = {
            "parameters": parameters,
            "form": form}

class ModeTab(QtGui.QWidget):
    def __init__(self, mode_id):
        self._mode_id = mode_id
        QtGui.QWidget.__init__(self)
