from receiver import SERVER_PORT_BVH
import argparse
import SocketServer
import time
import glob

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/../../movement_ai")
from bvh.bvh_collection import BvhCollection

parser = argparse.ArgumentParser()
parser.add_argument("bvh")
parser.add_argument("--port", type=int, default=SERVER_PORT_BVH)
parser.add_argument("--speed", type=float, default=1.0)
parser.add_argument("--ping-pong", action="store_true")
args = parser.parse_args()

bvh_filenames = glob.glob(args.bvh)
if len(bvh_filenames) == 0:
    raise Exception("no files found matching the pattern %s" % args.bvh)
print "loading BVHs from %s..." % args.bvh
bvh_reader = BvhCollection(bvh_filenames)
bvh_reader.read()
    
class PnSimulatorHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        while True:
            frame_index = looper.next_frame_index()
            frame = bvh_reader.get_frame_by_index(frame_index)
            line = "mock_ID mock_name " + " ".join([str(value) for value in frame])
            self.request.sendall("%s||\n" % line)
            time.sleep(bvh_reader.get_frame_time() / args.speed)

class NormalLooper:
    def __init__(self, num_frames):
        self._num_frames = num_frames
        self._t = 0

    def next_frame_index(self):
        result = self._t % self._num_frames
        self._t += 1
        return result
    
class PingPongLooper:
    def __init__(self, num_frames):
        self._num_frames = num_frames
        self._t = 0
        self._loop_length = num_frames * 2 - 2

    def next_frame_index(self):
        t_within_loop = self._t % self._loop_length
        if t_within_loop < self._num_frames:
            result = t_within_loop
        else:
            result = self._loop_length - t_within_loop
        self._t += 1
        return result
        
if args.ping_pong:
    looper = PingPongLooper(bvh_reader.get_num_frames())
else:
    looper = NormalLooper(bvh_reader.get_num_frames())

server = SocketServer.TCPServer(("localhost", args.port), PnSimulatorHandler)
server.allow_reuse_address = True
print "OK serving"
server.serve_forever()
