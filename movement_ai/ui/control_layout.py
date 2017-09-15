from PyQt4 import QtGui

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
