from receiver import SERVER_PORT_BVH
import argparse
import SocketServer
import time
import re

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/../../movement_ai")

parser = argparse.ArgumentParser()
parser.add_argument("bvh")
parser.add_argument("--port", type=int, default=SERVER_PORT_BVH)
parser.add_argument("--frame-rate", type=float, default=125)
parser.add_argument("--speed", type=float, default=1.0)
parser.add_argument("--ping-pong", action="store_true")
args = parser.parse_args()

def get_frames_from_bvh_file(filename):
    global frames, bvh_frame_time
    
    frames = []
    with open(filename) as f:
        for line in f:
            line = line.rstrip("\n")
            
            m = re.match("^Frame Time: ([0-9\.]+)$", line)
            if m:
                bvh_frame_time = float(m.group(1))
                break

        for line in f:
            line = line.rstrip("\n")
            frame = "mock_ID mock_name %s||\n" % line
            frames.append(frame)
    
class PnSimulatorHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        sending_start_time = time.time()
        num_frames_sent = 0
        while True:
            if num_frames_sent > 0:
                sending_fps = float(num_frames_sent) / (time.time() - sending_start_time)
                if sending_fps > args.frame_rate:
                    time.sleep(0.00001)
                    continue
                
            t = int((time.time() - start_time) / bvh_frame_time)
            frame_index = looper.get_frame_index(t)
            frame = frames[frame_index]
            self.request.sendall(frame)
            num_frames_sent += 1
            
class NormalLooper:
    def __init__(self, num_frames):
        self._num_frames = num_frames

    def get_frame_index(self, t):
        result = t % self._num_frames
        return result
    
class PingPongLooper:
    def __init__(self, num_frames):
        self._num_frames = num_frames
        self._loop_length = num_frames * 2 - 2

    def get_frame_index(self, t):
        t_within_loop = t % self._loop_length
        if t_within_loop < self._num_frames:
            result = t_within_loop
        else:
            result = self._loop_length - t_within_loop
        return result

get_frames_from_bvh_file(args.bvh)
num_frames = len(frames)

if args.ping_pong:
    looper = PingPongLooper(num_frames)
else:
    looper = NormalLooper(num_frames)

bvh_frame_time = bvh_frame_time / args.speed
sending_frame_time = 1. / args.frame_rate

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass

server = ThreadedTCPServer(("localhost", args.port), PnSimulatorHandler)
server.allow_reuse_address = True
print "OK serving"
start_time = time.time()
server.serve_forever()
