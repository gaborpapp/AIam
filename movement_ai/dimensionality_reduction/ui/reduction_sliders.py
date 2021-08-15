from .dimensionality_reduction_ui import *

class ReductionSliders(ReductionTab, QtWidgets.QWidget):
    def __init__(self, parent):
        ReductionTab.__init__(self, parent)
        QtWidgets.QWidget.__init__(self)
        self._layout = QtWidgets.QVBoxLayout()
        self._add_sliders()
        self._layout.addStretch(1)
        self.setLayout(self._layout)

    def slider(self, n):
        return self._sliders[n]

    def reduction_changed(self, normalized_reduction):
        self._update_sliders(normalized_reduction)

    def _update_sliders(self, normalized_reduction):
        for n in range(self._parent.get_num_reduced_dimensions()):
            self._sliders[n].setValue(self._normalized_reduction_value_to_slider_value(
                    n, normalized_reduction[n]))

    def _add_sliders(self):
        self._sliders = []
        for n in range(self._parent.get_num_reduced_dimensions()):
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, SLIDER_PRECISION)
            slider.setSingleStep(1)
            slider.setValue(self._normalized_reduction_value_to_slider_value(n, 0.5))
            slider.sliderMoved.connect(
                lambda: self._parent.reduction_changed_interactively(self))
            self._layout.addWidget(slider)
            self._sliders.append(slider)

    def set_enabled(self, enabled):
        for slider in self._sliders:
            slider.setEnabled(enabled)
            
    def _normalized_reduction_value_to_slider_value(self, n, value):
        return int(
            self.normalized_reduction_value_to_exploration_value(n, value) * SLIDER_PRECISION)

    def _slider_value_to_normalized_reduction_value(self, n, value):
        return self.exploration_value_to_normalized_reduction_value(
            n, float(value) / SLIDER_PRECISION)

    def get_normalized_reduction(self):
        normalized_reduction = numpy.array(
            [self._slider_value_to_normalized_reduction_value(n, self._sliders[n].value())
             for n in range(self._parent.get_num_reduced_dimensions())])
        return normalized_reduction
