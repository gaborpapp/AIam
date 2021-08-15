import threading
import socket
import struct
from . import osc
import logging

class OscSender:
    def __init__(self, port, host=None, log_filename=None, proto=osc.UDP):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._proto = proto
        if log_filename:
            raise Exception("log_filename not supported")
        if host is None:
            host = "localhost"
        if proto == osc.TCP:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((host, port))
        elif proto == osc.UDP:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            resolved_host = socket.gethostbyname(host)
            self._address = (resolved_host, port)
        self._lock = threading.Lock()
        self._status = True

    def send(self, address_pattern, *args):
        with self._lock:
            self._send(address_pattern, *args)

    def _send(self, address_pattern, *args):
        message = self._generate_message(address_pattern, *args)
        message = self._ensure_size_is_multiple_of_4(message)
        
        if self._proto == osc.TCP:
            size_int32 = struct.pack(">i", len(message))
            try:
                self._socket.send(size_int32)
            except Exception as exception:
                self._logger.error(exception, exc_info=True)
                self._status = False
                return
            self._status = True
            
        elif self._proto == osc.UDP:
            try:
                self._socket.sendto(message, self._address)
            except Exception as exception:
                self._logger.error(exception, exc_info=True)
                self._status = False
                return
            self._status = True

    def _generate_message(self, address_pattern, *args):
        message = self._osc_string(address_pattern)
        message += self._type_tag_string(args)
        for arg in args:
            message += self._arg(arg)
        return message

    def _ensure_size_is_multiple_of_4(self, string):
        while len(string) % 4 != 0:
            string += '\0'
        return string

    def _osc_string(self, string):
        return self._ensure_size_is_multiple_of_4(string + '\0')

    def _type_tag_string(self, values):
        return self._osc_string("," + "".join([self._type_tag(value) for value in values]))

    def _type_tag(self, value):
        if isinstance(value, int):
            return 'i'
        elif isinstance(value, float):
            return 'f'
        elif isinstance(value, str):
            return 's'
        else:
            raise Exception("unknown type tag for value '%s' of class %s" % (value, value.__class__))

    def _arg(self, value):
        if isinstance(value, int):
            return struct.pack(">l", value)
        elif isinstance(value, float):
            return struct.pack(">f", value)
        elif isinstance(value, str):
            return self._osc_string(value)
        else:
            raise Exception("don't know how to handle value '%s'" % value)

    def get_status(self):
        return self._status
