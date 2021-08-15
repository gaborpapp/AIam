from simple_osc_receiver import OscReceiver
import time
import pickle
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("name", type=str)
args = parser.parse_args()

def receive_torso_position(path, args, types, src, user_data):
    global first_input_time
    position_tuple = args
    if first_input_time is None:
        first_input_time = time.time()
    t = time.time() - first_input_time
    record_input(t, position_tuple)

def record_input(t, position_tuple):
    print(t, position_tuple)

first_input_time = None
osc_receiver = OscReceiver(7891, listen="localhost")
osc_receiver.add_method("/joint/torso", "fff", receive_torso_position)
osc_receiver.start(auto_serve=True)

while True:
    time.sleep(1)
