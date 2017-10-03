from PyQt4 import QtGui, QtCore

SLIDER_PRECISION = 1000

class SliderControl:
    def __init__(self, label, min_value, max_value, default_value, on_changed_value, label_precision=4):
        self._label = label
        self._min_value = float(min_value)
        self._max_value = float(max_value)
        self._range = max_value - min_value
        self._value_widget = QtGui.QLabel()
        self._value_widget.setFixedWidth(60)
        
        def create_slider():
            slider = QtGui.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, SLIDER_PRECISION)
            slider.setSingleStep(1)
            slider.setValue(self._value_to_slider_value(default_value))
            slider.valueChanged.connect(on_changed_slider_value)
            return slider

        def on_changed_slider_value(slider_value):
            value = self._slider_value_to_value(slider_value)
            update_value_widget(value)
            on_changed_value(value)

        def update_value_widget(value):
            format_string = "%%.%df" % label_precision
            self._value_widget.setText(format_string % value)

        self._slider = create_slider()
        update_value_widget(default_value)

    def _value_to_slider_value(self, value):
        return (value - self._min_value) / self._range * SLIDER_PRECISION

    def _slider_value_to_value(self, slider_value):
        return float(slider_value) / SLIDER_PRECISION * self._range + self._min_value

    @property
    def label(self):
        return self._label

    @property
    def slider(self):
        return self._slider

    @property
    def value(self):
        return self._slider_value_to_value(self._slider.value())
    
    @property
    def value_widget(self):
        return self._value_widget
        
    def set_value(self, value):
        self._slider.setValue(self._value_to_slider_value(value))

    def set_enabled(self, enabled):
        self._slider.setEnabled(enabled)

class CheckboxControl:
    def __init__(self, label, default_value, on_changed_value):
        self._label = label
        self._on_changed_value = on_changed_value
        self._checkbox = QtGui.QCheckBox()
        self._checkbox.setChecked(default_value)
        self._checkbox.stateChanged.connect(lambda: self._state_changed())

    @property
    def label(self):
        return self._label
        
    @property
    def checkbox(self):
        return self._checkbox

    def _state_changed(self):
        self._on_changed_value(self._checkbox.isChecked())

    def set_value(self, value):
        self._checkbox.setChecked(value)

    @property
    def value(self):
        return self._checkbox.isChecked()
    
class ControlLayout:
    def __init__(self):
        self._layout = QtGui.QGridLayout()
        self._row = 0

    @property
    def layout(self):
        return self._layout
    
    def add_label(self, string):
        label = QtGui.QLabel(string)
        self._layout.addWidget(label, self._row, 0)

    def add_control_widget(self, widget):
        self.add_control_widgets([widget])

    def add_control_widgets(self, widgets):
        row_span = 1
        if len(widgets) == 1:
            column_span = 2
            self._layout.addWidget(widgets[0], self._row, 1, row_span, column_span)
        elif len(widgets) == 2:
            column_span = 1
            self._layout.addWidget(widgets[0], self._row, 1, row_span, column_span)
            self._layout.addWidget(widgets[1], self._row, 2, row_span, column_span)
        self._row += 1

    def add_slider_row(self, *args, **kwargs):
        control = SliderControl(*args, **kwargs)
        self.add_label(control.label)
        self.add_control_widgets([control.slider, control.value_widget])
        return control

    def add_checkbox_row(self, *args, **kwargs):
        control = CheckboxControl(*args, **kwargs)
        self.add_label(control.label)
        self.add_control_widget(control.checkbox)
        return control
    
