from .dimensionality_reduction_ui import *

class FeatureSliders(QtWidgets.QWidget):
    def __init__(self, parent, feature_extractor):
        QtGui.QWidget.__init__(self)
        self._parent = parent
        self._feature_extractor = feature_extractor
        self._layout = QtGui.QFormLayout()
        self._add_sliders()
        self.setLayout(self._layout)
        self.set_enabled(False)

    def slider(self, n):
        return self._sliders[n]

    def features_changed(self, values):
        self._update_sliders(values)

    def _update_sliders(self, values):
        for n in range(self._feature_extractor.get_num_features()):
            self._sliders[n].setValue(self._feature_value_to_slider_value(
                    n, values[n]))

    def _add_sliders(self):
        self._sliders = []
        for n in range(self._feature_extractor.get_num_features()):
            slider = QtGui.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, SLIDER_PRECISION)
            slider.setSingleStep(1)
            slider.setValue(self._feature_value_to_slider_value(n, 0.5))
            slider.sliderMoved.connect(
                lambda: self._parent.features_changed_interactively())
            label = QtGui.QLabel(self._feature_extractor.FEATURES[n])
            self._layout.addRow(label, slider)
            self._sliders.append(slider)

    def set_enabled(self, enabled):
        for slider in self._sliders:
            slider.setEnabled(enabled)
            
    def _feature_value_to_slider_value(self, n, value):
        return int(value * SLIDER_PRECISION)

    def _slider_value_to_feature_value(self, n, value):
        return float(value) / SLIDER_PRECISION

    def get_features(self):
        return numpy.array(
            [self._slider_value_to_feature_value(n, self._sliders[n].value())
             for n in range(self._feature_extractor.get_num_features())])
