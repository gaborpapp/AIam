#!/usr/bin/env python

from svg_exporter import SvgExporter
import math
from argparse import ArgumentParser
import os

parser = ArgumentParser()
parser.add_argument("filename")
parser.add_argument("--camera-x", "-cx", type=float)
parser.add_argument("--camera-y", "-cy", type=float)
parser.add_argument("--camera-z", "-cz", type=float)
parser.add_argument("--rotation", "-r", type=float)
parser.add_argument("--output", "-o")
parser.add_argument("--frame-width", type=float, default=100)
parser.add_argument("--frame-height", type=float, default=100)
parser.add_argument("--stroke-width", type=float, default=1)
parser.add_argument("--begin", type=int)
parser.add_argument("--end", type=int)
parser.add_argument("--num-frames", type=int)
parser.add_argument("--displacement", type=float, default=0)
parser.add_argument("--min-opacity", type=float, default=0.1)
parser.add_argument("--constrain-floor", action="store_true")
parser.add_argument("--auto-crop", action="store_true")
parser.add_argument("--split", action="store_true")
args = parser.parse_args()

def write_svg(string):
    global output
    print(string, file=output)

if args.begin is None:
    begin = 1
else:
    begin = args.begin

if args.end is None:
    end = skeleton.frames + 1
else:
    end = args.end

if args.num_frames is None:
    num_frames = end - begin
else:
    num_frames = args.num_frames

print("exporting %s frames in the range %s-%s" % (num_frames, begin, end))

def write_header():
    write_svg('<svg xmlns="http://www.w3.org/2000/svg" version="1.1">')
    write_svg('<rect width="%f" height="%f" fill="white" />' % (
            args.frame_width + args.displacement * num_frames, args.frame_height))

def write_footer():
    write_svg('</svg>')

def opacity(n, relative_frame_index):
    if args.split:
        return 1
    else:
        return args.min_opacity + (1 - args.min_opacity) * math.pow(relative_frame_index, 3)
    # if (n-2) % 5 == 0:
    #     return 1
    # else:
    #     return args.min_opacity

if not args.split:
    if args.output:
        output_path = args.output
    else:
        output_path = args.filename.replace(".bvh", ".svg")
    output = open(output_path, "w")
    write_header()

exporter = SvgExporter(args.filename, args.camera_x, args.camera_y, args.camera_z)

for n in range(num_frames):
    relative_frame_index = float(n) / num_frames
    frame_index = begin + int(relative_frame_index * (end - begin))
    print("adding frame %s" % frame_index)
    x_offset = args.displacement * n

    if args.split:
        output_path = "%s_%03d.svg" % (args.filename.replace(".bvh", ""), n)
        output = open(output_path, "w")
        write_header()

    exporter.export_frame(
        output,
        frame_index,
        args.frame_width, args.frame_height,
        opacity(n, relative_frame_index),
        x_offset,
        args.constrain_floor,
        args.auto_crop,
        args.stroke_width)

    if args.split:
        write_footer()
        output.close()

if not args.split:
    write_footer()
    output.close()
