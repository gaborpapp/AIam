from audio import *
import time
from math import sqrt

import tornado.web
import tornado.ioloop
import tornado.websocket
from tornado.httpserver import HTTPServer

s = create_audio_server().boot()
s.amp = 0.1
sine_left = Sine()
sine_right = Sine()
left = sine_left.out()
right = sine_right.out(1)

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/../dance-cognition")
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/../dance-cognition/connectivity")
from osc_receiver import OscReceiver

WEBSOCKET_APPLICATION = "/ifself"
WEBSOCKET_PORT = 15001
OSC_PORT = 15002

min_freq = 50
max_freq = 500
center = [132,4500]
area_radius = 1000 
max_distance_to_border = 1000

def update_sound(relative_distance_to_border):
        freq = min_freq + (max_freq - min_freq) * relative_distance_to_border
        sine_left.setFreq(freq)
        sine_right.setFreq(freq)

update_sound(1)

def distance(p0, p1):
    return sqrt((p0[0] - p1[0])**2 + (p0[1] - p1[1])**2)

def handle_center(path, values, types, src, user_data):
	global area_radius
        global s
	user_id, x, y, z = values
	center_distance = distance([x,z], center)
        distance_to_border = abs(center_distance - area_radius)
        relative_distance_to_border = min(distance_to_border / max_distance_to_border, 1)
        print relative_distance_to_border
        update_sound(relative_distance_to_border)
        send_to_websocket_clients(str(relative_distance_to_border))

def send_to_websocket_clients(string):
        for client_handler in websocket_server.client_handlers:
                client_handler.write_message(string)

osc_receiver = OscReceiver(OSC_PORT)
osc_receiver.add_method("/center", "ifff", handle_center)
osc_receiver.start()

class ClientHandler(tornado.websocket.WebSocketHandler):
    def __init__(self, server, request, **kwargs):
        super(ClientHandler, self).__init__(server, request, **kwargs)
        self._server = server
        server.client_handlers.add(self)

    def on_close(self):
        self._server.client_handlers.remove(self)

    def check_origin(self, origin):
        return True

    def allow_draft76(self):
        return True

class WebsocketServer(tornado.web.Application):
    def __init__(self, client_handler=ClientHandler, settings={}):
        tornado.web.Application.__init__(
            self,
            [(WEBSOCKET_APPLICATION, client_handler, settings)],
            debug=True)
        self._loop = tornado.ioloop.IOLoop.instance()
        self._listen(WEBSOCKET_PORT)
        self.client_handlers = set()

    def _listen(self, port, address="", **kwargs):
        self._server = HTTPServer(self, **kwargs)
        self._server.listen(port, address)

    def start(self):
        self._loop.start()

    def stop(self):
        self._loop.stop()
        self._server.stop()

s.start()
websocket_server = WebsocketServer()
websocket_server.start()
