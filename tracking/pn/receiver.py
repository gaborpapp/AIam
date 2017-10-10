#!/usr/bin/env python

# Output Format:
# Displacement should be enabled

# Broadcasting:
# BVH should be enabled, with string format

SERVER_PORT_BVH = 7001
MAX_TIME_FOR_BLOCKING_RECV = 3.0

import socket
import time

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
        self._socket.settimeout(0.001)
        self._name = "%s for %s:%s" % (self.__class__.__name__, host, port)

    def get_frames(self):
        self._should_stop = False
        for line in self._readlines(delim='||'):
            yield self._process_pn_bvh_line(line)

    def _readlines(self, buffer_size=1024, delim='\n'):
        buffer = ''
        data = True
        would_block_exception = socket.error
        self._time_of_last_blocking_recv = time.time()
        while data and not self._should_stop:
            now = time.time()
            try:
                data = self._socket.recv(buffer_size)
            except would_block_exception:
                self._time_of_last_blocking_recv = now
                continue

            self._warn_about_lag_if_no_recent_recv_would_block(now)
            buffer += data

            while buffer.find(delim) != -1:
                line, buffer = buffer.split(delim, 1)
                yield line

        if self._should_stop:
            self._dispatch_status_message("Stopped. Disconnecting.")
            try:
                self._socket.close()
            except socket.error:
                pass
        else:
            self._dispatch_status_message("Remote peer shut down.")
            raise RemotePeerShutDown()

    def _warn_about_lag_if_no_recent_recv_would_block(self, now):
        time_since_last_emptied_buffer = now - self._time_of_last_blocking_recv
        if time_since_last_emptied_buffer > MAX_TIME_FOR_BLOCKING_RECV:
            self._dispatch_status_message(
                "Warning: %.1fs since socket.recv would block. This may indicate a lag." % \
                time_since_last_emptied_buffer)
            self._postpone_next_lag_warning(now)

    def _postpone_next_lag_warning(self, now):
        self._time_of_last_blocking_recv = now
        
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

    def stop(self):
        self._should_stop = True

    def _dispatch_status_message(self, message):
        decorated_message = "%s: %s" % (self._name, message)
        self.on_status_message(decorated_message)
        
    def on_status_message(self, message):
        print message
