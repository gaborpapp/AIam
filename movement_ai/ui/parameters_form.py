from PyQt4 import QtCore, QtGui
from control_layout import ControlLayout
from parameters import *

SLIDER_PRECISION = 1000

class ParametersForm:
    def __init__(self, parameters, parent=None, control_layout=None):
        if control_layout is None:
            self._control_layout = ControlLayout()
        else:
            self._control_layout = control_layout
        self._field_widgets = {}
        self._value_widgets = {}
        self._row = 0
        for parameter in parameters:
            field_widget = self._create_parameter_field(parameter)
            self._field_widgets[parameter.name] = field_widget
            self._control_layout.add_label(parameter.name)
            if isinstance(field_widget, Slider):
                value_widget = QtGui.QLabel()
                value_widget.setFixedWidth(30)
                self._control_layout.add_control_widgets([field_widget, value_widget])
                self._value_widgets[parameter.name] = value_widget
                self._update_value_widget(parameter)
            else:
                self._control_layout.add_control_widget(field_widget)                
            self._row += 1
        if control_layout is None:
            parent.addLayout(self._control_layout.layout)

    def _create_parameter_field(self, parameter):
        if parameter.choices is not None:
            if parameter.choices.__class__ is ParameterFloatRange:
                field = Slider(self, parameter)
            else:
                field = ListChoice(parameter)
        elif parameter.type == str:
            field = LineEdit(parameter)
        elif parameter.type in [int, float]:
            field = LineEdit(parameter)
        else:
            raise Exception("don't know how to create field for %s" % parameter)
        field.update_to_reflect_value()
        return field

    def update_field_to_reflect_changed_value(self, parameter):
        field_widget = self._field_widgets[parameter.name]
        field_widget.update_to_reflect_value()
        self.value_changed(parameter)

    def value_changed(self, parameter):
        self._update_value_widget(parameter)

    def _update_value_widget(self, parameter):
        if parameter.name in self._value_widgets:
            value_widget = self._value_widgets[parameter.name]
            value_widget.setText("%.2f" % parameter.value())

class Slider(QtGui.QSlider):
    def __init__(self, form, parameter):
        self._form = form
        self._parameter = parameter
        QtGui.QSlider.__init__(self, QtCore.Qt.Horizontal)
        self.setRange(0, SLIDER_PRECISION)
        self.setSingleStep(1)
        self.sliderMoved.connect(lambda value: self._slider_value_changed(parameter, value))

    def _parameter_value_to_slider_value(self, parameter):
        return int((parameter.value() - parameter.choices.min_value) / \
            parameter.choices.range * SLIDER_PRECISION)

    def _slider_value_to_parameter_value(self, parameter, slider_value):
        return float(slider_value) / SLIDER_PRECISION * parameter.choices.range + \
            parameter.choices.min_value
        
    def _slider_value_changed(self, parameter, slider_value):
        value = self._slider_value_to_parameter_value(parameter, slider_value)
        parameter.set_value(value)
        self._form.value_changed(parameter)

    def update_to_reflect_value(self):
        self.setValue(self._parameter_value_to_slider_value(self._parameter))

class ListChoice(QtGui.QComboBox):
    def __init__(self, parameter):
        self._parameter = parameter
        QtGui.QComboBox.__init__(self)
        for value in parameter.choices:
            self.addItem(value)
        self.activated.connect(
            lambda value: self._edited_choice_parameter(parameter, value))

    def _edited_choice_parameter(self, parameter, index):
        parameter.set_value(parameter.choices[index])

    def update_to_reflect_value(self):
        index = 0
        for value in self._parameter.choices:
            if self._parameter.value() == value:
                self.setCurrentIndex(index)
                return
            index += 1

class LineEdit(QtGui.QLineEdit):
    def __init__(self, parameter):
        self._parameter = parameter
        QtGui.QLineEdit.__init__(self)
        self.textEdited.connect(lambda value: self._edited_text_parameter(parameter, value))

    def _edited_text_parameter(self, parameter, string):
        if string == "":
            return
        if parameter.type == int:
            parameter.set_value(int(string))
        elif parameter.type == float:
            parameter.set_value(float(string))

    def update_to_reflect_value(self):
        self.setText(str(self._parameter.value()))
