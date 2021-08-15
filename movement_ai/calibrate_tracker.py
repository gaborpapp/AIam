import pickle
from argparse import ArgumentParser
from vector import Vector3d
import math

CONFIDENCE_THRESHOLD = 0.5

parser = ArgumentParser()
parser.add_argument("--log-source")
args = parser.parse_args()

foot_positions = list()

def process_log_entry(path, values):
    if path == "/joint":
        user_id, joint_name, x, y, z, confidence = values
        if joint_name in ["left_foot", "right_foot"] and confidence > CONFIDENCE_THRESHOLD:
            foot_positions.append(Vector3d(x, y, z))

f = open(args.log_source, "r")
try:
    while True:
        (t, path, args) = pickle.load(f)
        process_log_entry(path, args)
except EOFError:
    pass
f.close()

def median(values):
    return sorted(values)[len(values)/2]

def pitch_angle(position, tracker_y_position):
    y = position.y - tracker_y_position
    d = math.sqrt(position.x * position.x + position.z * position.z + y*y)
    return math.asin(y / d)

def shift_y(position, tracker_pitch, tracker_y_position):
    y = position.y - tracker_y_position
    d = math.sqrt(position.x * position.x + position.z * position.z + y*y)
    a = math.asin(y / d)
    return math.sin(a + tracker_pitch) * d

def measure_error(tracker_pitch, tracker_y_position):
    shifted_y_values = [shift_y(position, tracker_pitch, tracker_y_position)
                        for position in foot_positions]
    return sum([y*y for y in shifted_y_values])
    
tracker_pitch = 0
tracker_y_position = 0

pitch_step = .01
y_step = 10.
comparisons = [
    {"pitch": pitch_step, "y": 0},
    {"pitch": -pitch_step, "y": 0},
    {"pitch": 0, "y": y_step},
    {"pitch": 0, "y": -y_step},
    {"pitch": pitch_step, "y": y_step},
    {"pitch": -pitch_step, "y": y_step},
    {"pitch": pitch_step, "y": -y_step},
    {"pitch": -pitch_step, "y": -y_step},
    ]
min_y_step = 1
speed = 1.

lowest_error = None
while speed > 0.1:
    errors = [(comparison,
               measure_error(tracker_pitch + comparison["pitch"] * speed,
                             tracker_y_position + comparison["y"] * speed))
              for comparison in comparisons]
    best_comparison, min_error = min(errors, key=lambda comparison_error: comparison_error[1])
    if lowest_error is not None and min_error > lowest_error:
        print("slowing down")
        speed /= 2
    else:
        print("error: %.3f  tracker: %.3f,%.3f" % (
            min_error, -tracker_y_position, -math.degrees(tracker_pitch)))
        tracker_pitch += best_comparison["pitch"] * speed
        tracker_y_position += best_comparison["y"] * speed
        lowest_error = min_error

print("finished calibration")
