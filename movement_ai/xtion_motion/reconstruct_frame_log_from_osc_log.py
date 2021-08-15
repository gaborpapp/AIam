import argparse
import pickle

MIN_DURATION_BETWEEN_FRAMES = 0.01

parser = argparse.ArgumentParser()
parser.add_argument("osc_log")
parser.add_argument("output")
args = parser.parse_args()

def start_new_frame(t):
    global frame
    frame = {"timestamp": t * 1000,
             "states": [],
             "joint_data": []}

def add_to_current_frame(path, values):
    global frame
    if path == "/state":
        frame["states"].append(values)
    elif path == "/joint":
        frame["joint_data"].append(values)
    else:
        raise Exception("unexpected path %r" % path)

def append_frame_to_output():
    global frame, output_file
    output_file.write(pickle.dumps(frame))

frame = None
input_file = open(args.osc_log)
output_file = open(args.output, "w")
previous_time = None
try:
    while True:
        t, path, values = pickle.load(input_file)
        if previous_time is None:
            start_new_frame(t)
        else:
            delta_t = t - previous_time
            if delta_t > MIN_DURATION_BETWEEN_FRAMES:
                if frame is not None:
                    append_frame_to_output()
                start_new_frame(t)
        add_to_current_frame(path, values)
        previous_time = t
except EOFError:
    pass

if frame is not None:
    append_frame_to_output()

