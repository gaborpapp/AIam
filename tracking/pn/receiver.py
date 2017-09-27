#!/usr/bin/env python

# Output Format:
# Displacement should be enabled

# Broadcasting:
# BVH should be enabled, with string format

SERVER_PORT_BVH = 7001

import socket

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/../../movement_ai")
from fps_meter import FpsMeter

class RemotePeerShutDown(Exception):
    pass

class PnReceiver:
    def __init__(self):
        self._fps_meter = FpsMeter("PnReceiver")
        
    def connect(self, host, port):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((host, port))

    def get_frames(self):
        for line in self._readlines(delim='||'):
            yield self._process_pn_bvh_line(line)

    def _readlines(self, buffer_size=1024, delim='\n'):
        buffer = ''
        data = True
        while data:
            data = self._socket.recv(buffer_size)
            buffer += data

            while buffer.find(delim) != -1:
                line, buffer = buffer.split(delim, 1)
                yield line
        raise RemotePeerShutDown()
    
    def _process_pn_bvh_line(self, line):
        values_as_strings = line.split(" ")
        # print values_as_strings
        values_as_strings = values_as_strings[2:] # skip ID (?) and name
        values_as_floats = [float(string)
                            for string in values_as_strings
                            if len(string) > 0]
        self._fps_meter.update()
        self.on_fps_changed(self._fps_meter.get_fps())
        return values_as_floats

    def on_fps_changed(self, fps):
        pass
