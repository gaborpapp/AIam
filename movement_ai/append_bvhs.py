#!/usr/bin/env python

import sys
import re

if len(sys.argv) < 3:
    print("Usage: %s input1.bvh input2.bvh ... output.bvh")
    sys.exit(-1)

input_paths = sys.argv[1:-1]
output_path = sys.argv[-1]

print("%d inputs: %s" % (len(input_paths), input_paths))
print("Output: %s" % output_path)

def add_header(input_path):
    for line in open(input_path):
        line = line.rstrip("\r\n")
        if line == "MOTION":
            return
        print(line, file=output)

def add_motion_data(input_path):
    in_motion_data = False
    for line in open(input_path):
        line = line.rstrip("\r\n")
        if in_motion_data:
            print(line, file=output)
        if line.startswith("Frame Time:"):
            in_motion_data = True

def get_num_frames(input_path):
    for line in open(input_path):
        line = line.rstrip("\r\n")
        m = re.match('^Frames:\s+(\d+)$', line)
        if m:
            return int(m.group(1))
    raise Exception("failed to get num frames for input file %r" % input_path)

def get_frame_time(input_path):
    for line in open(input_path):
        line = line.rstrip("\r\n")
        m = re.match('^Frame Time:\s+([\d.]+)$', line)
        if m:
            return float(m.group(1))
    raise Exception("failed to get frame time for input file %r" % input_path)

num_frames = sum([get_num_frames(input_path) for input_path in input_paths])
output = open(output_path, "w")
add_header(input_paths[0])
print("MOTION", file=output)
print("Frames: %d" % num_frames, file=output)
print("Frame Time: %f" % get_frame_time(input_paths[0]), file=output)
for input_path in input_paths:
    add_motion_data(input_path)
