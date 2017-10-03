import json

class Parameter:
    def __init__(self, name, get_value, set_value):
        self.name = name
        self.get_value = get_value
        self.set_value = set_value

class PresetManager:
    def __init__(self):
        self._parameters = {}
        self._on_changeds = {}

    def add_parameter(self, name, get_value, set_value):
        self._parameters[name] = Parameter(name, get_value, set_value)

    def save(self, path):
        name_value_dict = dict((parameter.name, parameter.get_value())
                               for parameter in self._parameters.values())
        with open(path, "w") as f:
            json.dump(name_value_dict, f)

    def load(self, path):
        with open(path, "r") as f:
            name_value_dict = json.load(f)
        for name, value in name_value_dict.iteritems():
            self._parameters[name].set_value(value)
