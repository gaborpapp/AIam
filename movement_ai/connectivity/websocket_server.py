import tornado.web
import tornado.ioloop
import tornado.websocket
from tornado.httpserver import HTTPServer
from event import Event
from connectivity.event_packing import EventPacker

WEBSOCKET_APPLICATION = "/aiam"
WEBSOCKET_PORT = 15001

class ClientHandler(tornado.websocket.WebSocketHandler):
    def __init__(self, server, request, **kwargs):
        super(ClientHandler, self).__init__(server, request, **kwargs)
        self.subscribed_events = []
        self._server = server
        server.client_handlers.add(self)

    def on_close(self):
        self._server.client_handlers.remove(self)
        
    def on_message(self, message):
        event = EventPacker.unpack(str(message))
        self._handle_event(event)

    def _handle_event(self, event):
        if event.type == Event.SUBSCRIBE:
            self.subscribed_events = event.content
            self.registered()
        else:
            self.received_event(event, self)
        
    def send_event(self, event):
        if event.type in self.subscribed_events:
            self.write_message(EventPacker.pack(event))

    def registered(self):
        pass

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

    def add_periodic_callback(self, callback, callback_time):
        periodic_callback = tornado.ioloop.PeriodicCallback(callback, callback_time, self._loop)
        periodic_callback.start()

    def client_subscribes_to(self, event_type):
        for handler in self.client_handlers:
            if event_type in handler.subscribed_events:
                return True
