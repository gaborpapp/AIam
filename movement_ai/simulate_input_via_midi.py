import rtmidi
from rtmidi.midiutil import open_midiport
import time

class MidiInterpreter:
    def __init__(self, output_controller, command=None, channel=None, midi_port=None, calibrate=False):
        self._output_controller = output_controller
        self._tracked_command = command
        self._tracked_channel = channel
        self._calibrate = calibrate
        self._midi_in, port_name = open_midiport(midi_port, "input")
        self._midi_in.set_callback(self._callback)

    def _callback(self, event, data=None):
        message, deltatime = event
        command, channel, value = message
        if self._calibrate:
            print("command=%s channel=%s" % (command, channel))
        if command == self._tracked_command and channel == self._tracked_channel:
            self._process_value(value)

    def _process_value(self, value):
        relative_intensity = float(value) / 127
        self._output_controller.send_user_intensity(relative_intensity)
        
    def main_loop(self):
        print("press ctrl-c to exit")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        self._midi_in.close_port()
