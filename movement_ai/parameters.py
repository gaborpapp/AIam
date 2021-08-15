class Parameter:
    def __init__(self, parameters, name, type=str, default=None, choices=None):
        self.parameters = parameters
        self.name = name
        self.type = type
        self.default = default
        self.choices = choices
        self._value = default

    def value(self):
        return self._value

    def set_value(self, value, notify=True):
        self._value = value
        if notify:
            self.parameters.notify_changed(self)

    def __repr__(self):
        return "Parameter(name=%s, type=%s, default=%s, choices=%s)" % (
            self.name, self.type, self.default, self.choices)

    def add_parser_argument(self, parser):
        parser.add_argument("--%s" % self.name, type=self.type)

    def set_value_from_arg(self, arg):
        if arg is not None:
            self._value = arg

class Parameters:
    def __init__(self):
        self._parameters = []
        self._parameters_by_name = {}
        self._listeners = set()

    def add_listener(self, listener):
        self._listeners.add(listener)

    def remove_listener(self, listener):
        self._listeners.remove(listener)

    def add_parameter(self, *args, **kwargs):
        parameter = Parameter(self, *args, **kwargs)
        self._parameters.append(parameter)
        self._parameters_by_name[parameter.name] = parameter
        return parameter

    def __getattr__(self, name):
        if name in self._parameters_by_name:
            return self._parameters_by_name[name].value()
        else:
            raise AttributeError("%r not among %r" % (name, list(self._parameters_by_name.keys())))

    def get_parameter(self, name):
        return self._parameters_by_name[name]

    def __iter__(self):
        return self._parameters.__iter__()

    def __len__(self):
        return len(self._parameters)
    
    def notify_changed(self, parameter):
        for listener in self._listeners:
            listener(parameter)

    def notify_changed_all(self):
        for parameter in self._parameters:
            self.notify_changed(parameter)

    def add_parser_arguments(self, parser):
        for parameter in self._parameters:
            parameter.add_parser_argument(parser)

    def set_values_from_args(self, args):
        for parameter in self._parameters:
            if hasattr(args, parameter.name):
                parameter.set_value_from_arg(getattr(args, parameter.name))

class ParameterFloatRange:
    def __init__(self, min_value, max_value):
        self.min_value = min_value
        self.max_value = max_value
        self.range = max_value - min_value
