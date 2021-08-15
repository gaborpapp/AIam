import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/connectivity")

from argparse import ArgumentParser
import rtmidi
from rtmidi.midiutil import open_midiport
import time
from websocket_client import WebsocketClient
from event_listener import EventListener
from event import Event
from dimensionality_reduction.behaviors.hybrid import HybridParameters
from parameters import *

WEBSOCKET_HOST = "localhost"
PARAMETERS = HybridParameters()

class MidiController:
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("--port")
        parser.add_argument("--calibrate", action="store_true")
        for parameter in PARAMETERS:
            if parameter.choices.__class__ is ParameterFloatRange:
                parser.add_argument("--%s" % parameter.name, help="command,channel")

    def __init__(self, args):
        self._args = args
        self._midi_in, port_name = open_midiport(args.port, "input")
        self._midi_in.set_callback(self._callback)
        self._create_parameter_lookup_table()

    def _create_parameter_lookup_table(self):
        self._parameter_lookup_table = {}
        for parameter in PARAMETERS:
            command_comma_channel = getattr(self._args, parameter.name)
            if command_comma_channel:
                self._parameter_lookup_table[command_comma_channel] = parameter

    def _callback(self, event, data=None):
        message, deltatime = event
        command, channel, value = message
        command_comma_channel = "%s,%s" % (command, channel)
        if self._args.calibrate:
            print(command_comma_channel)
        if command_comma_channel in self._parameter_lookup_table:
            parameter = self._parameter_lookup_table[command_comma_channel]
            self._process_value(parameter, value)

    def _process_value(self, parameter, midi_value):
        parameter_value = float(midi_value) / 127 * parameter.choices.range + \
            parameter.choices.min_value
        event_sender.send_event(
            Event(Event.PARAMETER,
                  {"class": "HybridParameters",
                   "name": parameter.name,
                   "value": parameter_value}))
                
    def main_loop(self):
        print("press ctrl-c to exit")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        self._midi_in.close_port()

parser = ArgumentParser()
MidiController.add_parser_arguments(parser)
args = parser.parse_args()

event_sender = WebsocketClient(WEBSOCKET_HOST)
event_sender.set_event_listener(EventListener())
event_sender.connect()

controller = MidiController(args)
controller.main_loop()
