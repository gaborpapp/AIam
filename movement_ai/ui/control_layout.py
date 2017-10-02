from PyQt4 import QtGui, QtCore

SLIDER_PRECISION = 1000

class Control:
    def __init__(self, label, max_value, default_value, on_changed_value, label_precision=4):
        self._label = label
        self._max_value = max_value
        self._value_widget = QtGui.QLabel()
        self._value_widget.setFixedWidth(60)
        
        def create_slider():
            slider = QtGui.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, SLIDER_PRECISION)
            slider.setSingleStep(1)
            slider.setValue(default_value / max_value * SLIDER_PRECISION)
            slider.valueChanged.connect(on_changed_slider_value)
            return slider

        def on_changed_slider_value(slider_value):
            value = float(slider_value) / SLIDER_PRECISION * max_value
            update_value_widget(value)
            on_changed_value(value)

        def update_value_widget(value):
            format_string = "%%.%df" % label_precision
            self._value_widget.setText(format_string % value)

        self._slider = create_slider()
        update_value_widget(default_value)

    @property
    def label(self):
        return self._label

    @property
    def slider(self):
        return self._slider

    @property
    def value_widget(self):
        return self._value_widget
        
    def set_value(self, value):
        self._slider.setValue(value / self._max_value * SLIDER_PRECISION)

    def set_enabled(self, enabled):
        self._slider.setEnabled(enabled)
        
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
        control = Control(*args, **kwargs)
        self.add_label(control.label)
        self.add_control_widgets([control.slider, control.value_widget])
        return control
