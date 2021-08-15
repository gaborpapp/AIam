import imp
from states import state_machine
from vector import *

def load_config(name=None):
    if name is None:
        name = "default"
    config = imp.load_source("config", _filename(name))
    config.center = Vector3d(*config.center)
    config.size = Vector3d(*config.size)
    state_machine.set_config(config)
    return config

def save_config(config, name):
    if name is None:
        raise Exception("cannot overwrite default config")
    f = open(_filename(name), "w")
    f.write('center = %r\n' % config.center.v)
    f.write('size = %r\n' % config.size.v)
    f.write('states = {\n')
    for state_name in list(state_machine.states.keys()):
        f.write('  %r: %r,\n' % (state_name, config.states[state_name]))
    f.write('}\n')
    f.close()

def _filename(name):
    return "input_data/%s/config.py" % name
