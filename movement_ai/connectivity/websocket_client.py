import ws4py.client.threadedclient
from connectivity.websocket_server import WEBSOCKET_PORT, WEBSOCKET_APPLICATION
from event import Event
from connectivity.event_packing import EventPacker
import contextlib
from tornado.stack_context import StackContext
import time

class WebsocketClient(ws4py.client.threadedclient.WebSocketClient):
    def __init__(self, host):
        address = "ws://%s:%s%s" % (host, WEBSOCKET_PORT, WEBSOCKET_APPLICATION)
        ws4py.client.threadedclient.WebSocketClient.__init__(self, address)
        self._event_listener = self

    def opened(self):
        print("connected to server")
        self.send_event(Event(Event.SUBSCRIBE, self._event_listener.get_handled_events()))

    def closed(self, code, reason=None):
        print("connection to server was closed (code=%r reason=%r)" % (code, reason))

    def connect(self):
        try:
            ws4py.client.threadedclient.WebSocketClient.connect(self)
        except KeyboardInterrupt:
            self.close()
        except:            
            time.sleep(2)
            print("connection failed - attempting reconnect")
            self.connect()

    @contextlib.contextmanager
    def _print_exception(self):
        try:
            yield
        except Exception as exception:
            print("received_message failed: %s" % exception)

    def received_message(self, message):
        with StackContext(self._print_exception):
            event = EventPacker.unpack(str(message))
            self._event_listener.received_event(event)

    def received_event(self, event):
        pass

    def send_event(self, event):
        packed_event = EventPacker.pack(event)
        try:
            self.send(packed_event)
        except:
            print("send_event failed - attempting reconnect")
            ws4py.client.threadedclient.WebSocketClient.__init__(self, self.url)
            self.connect()

    def set_event_listener(self, event_listener):
        self._event_listener = event_listener
