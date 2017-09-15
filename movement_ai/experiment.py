import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))+"/..")

from argparse import ArgumentParser
import storage
from bvh.bvh_collection import BvhCollection
import imp
from stopwatch import Stopwatch
from fps_meter import FpsMeter
import threading
from event import Event
from event_listener import EventListener
from bvh.bvh_writer import BvhWriter
import glob
import subprocess
import tracking.pn.receiver
import random
import numpy

from connectivity.websocket_server import WebsocketServer, ClientHandler
from connectivity.websocket_client import WebsocketClient
from connectivity.single_process_server import SingleProcessServer
from connectivity.single_process_client import SingleProcessClient

class BaseEntity:
    @staticmethod
    def add_parser_arguments(parser):
        pass

    def __init__(self, bvh_reader, pose, floor, z_up, args):
        self._t = 0
        self.bvh_reader = bvh_reader
        self.args = args
        self.model = None
        self.pose = pose
        self.floor = floor
        self.z_up = z_up
        self.processed_input = None

    def adapt_value_to_model(self, value):
        return value

    def proceed(self, time_increment):
        self._t += time_increment

    def process_input(self, value):
        return self.process_io(value)

    def process_output(self, value):
        return self.process_io(value)

    def process_io_blend(self, value, amount):
        return self.process_io(value)
    
    def process_io(self, value):
        return value

    def update(self, input=None):
        if input is None:
            self.processed_input = None
        else:
            self.processed_input = self.process_input(input)

    def get_cursor(self):
        if hasattr(self, "get_duration"):
            return self._t % self.get_duration()
        else:
            return self._t

    def set_cursor(self, t):
        self._t = t

    def get_last_root_vertical_orientation(self):
        return None

    def get_value_length(self):
        return len(self.get_value())

    def interpolate(self, x, y, amount):
        return numpy.array(y) * amount + \
            numpy.array(x) * (1-amount)
    
class Experiment(EventListener):
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("-profile", "-p")
        parser.add_argument("-entity", type=str)
        parser.add_argument("-train", action="store_true")
        parser.add_argument("-training-data", type=str)
        parser.add_argument("-training-duration", type=float)
        parser.add_argument("-training-data-frame-rate", type=int, default=50)
        parser.add_argument("-bvh", type=str,
                            help="If provided, this specifies both the skeleton and the training data.")
        parser.add_argument("-bvh-speed", type=float, default=1.0)
        parser.add_argument("-skeleton", type=str)
        parser.add_argument("-joint")
        parser.add_argument("-frame-rate", type=float, default=50.0)
        parser.add_argument("-unit-cube", action="store_true")
        parser.add_argument("-input-y-offset", type=float, default=.0)
        parser.add_argument("-output-y-offset", type=float, default=.0)
        parser.add_argument("-export-dir", default="export")
        parser.add_argument("--floor", action="store_true")
        parser.add_argument("--backend-only", action="store_true")
        parser.add_argument("--ui-only", action="store_true")
        parser.add_argument("--backend-host", default="localhost")
        parser.add_argument("--websockets", action="store_true",
                            help="Force websockets support (enabled automatically by --backend-only)")
        parser.add_argument("--no-websockets", action="store_true",
                            help="Force running without websockets support (e.g when combing --ui-only and --event-log-source)")
        parser.add_argument("--launch-when-ready", help="Run command when websocket server ready")
        parser.add_argument("--output-receiver-host")
        parser.add_argument("--output-receiver-port", type=int, default=10000)
        parser.add_argument("--output-receiver-type", choices=["bvh", "world"], default="bvh")
        parser.add_argument("--with-profiler", action="store_true")
        parser.add_argument("--z-up", action="store_true", help="Use Z-up for BVHs")
        parser.add_argument("--show-fps", action="store_true")
        parser.add_argument("--receive-from-pn", action="store_true")
        parser.add_argument("--pn-host", default="localhost")
        parser.add_argument("--pn-port", type=int, default=tracking.pn.receiver.SERVER_PORT_BVH)
        parser.add_argument("--random-seed", type=int)
        parser.add_argument("--start-frame", type=int)
        parser.add_argument("--deterministic", action="store_true",
                            help="Handle time deterministically (fixed time interval between updates) rather than taking " +
                            "real time into account. May cause latency.")
        parser.add_argument("--stopped", action="store_true", help="Start in stopped mode")

    def __init__(self, parser, event_handlers={}):
        event_handlers.update({
            Event.START: self._start,
            Event.STOP: self._stop,
            Event.START_EXPORT_BVH: self._start_export_bvh,
            Event.STOP_EXPORT_BVH: self._stop_export_bvh,
            Event.SET_CURSOR: lambda event: self.update_cursor(event.content),
            Event.PROCEED_TO_NEXT_FRAME: self._proceed_to_next_frame,
            Event.SAVE_STUDENT: self._save_student,
            Event.LOAD_STUDENT: self._load_student,
            Event.SET_FRICTION: lambda event: self.set_friction(event.content),
            Event.SET_LEARNING_RATE: lambda event: self.student.set_learning_rate(event.content),
            Event.SET_MODEL_NOISE_TO_ADD: self._set_model_noise_to_add,
            Event.SET_MIN_TRAINING_LOSS: self._set_min_training_loss,
            Event.SET_MAX_ANGULAR_STEP: lambda event: self.entity.set_max_angular_step(
                event.content),
        })
        EventListener.__init__(self, handlers=event_handlers)

        args, _remaining_args = parser.parse_known_args()

        if args.random_seed is not None:
            random.seed(args.random_seed)
            
        if args.profile:
            profile_path = "%s/%s.profile" % (self.profiles_dir, args.profile)
            profile_args_string = open(profile_path).read()
            profile_args_strings = profile_args_string.split()
            args, _remaining_args = parser.parse_known_args(profile_args_strings, namespace=args)
            self._student_model_path = "%s/%s.model" % (self.profiles_dir, args.profile)
            self._entity_model_path = "%s/%s.entity.model" % (self.profiles_dir, args.profile)
            self._training_data_path = "%s/%s.data" % (self.profiles_dir, args.profile)

        entity_module = imp.load_source("entity", "entities/%s.py" % args.entity)
        if hasattr(entity_module, "Entity"):
            self.entity_class = entity_module.Entity
        else:
            self.entity_class = BaseEntity
        self.entity_class.add_parser_arguments(parser)
        if not args.backend_only:
            self._entity_scene_module = imp.load_source("entity", "entities/%s_scene.py" % args.entity)
            self._entity_scene_module.Scene.add_parser_arguments(parser)
            self.add_ui_parser_arguments(parser)

        self.add_parser_arguments_second_pass(parser, args)
        args = parser.parse_args()
        if args.profile:
            args = parser.parse_args(profile_args_strings, namespace=args)

        self.args = args

        skeleton_bvh_path = self._get_skeleton_bvh_path()
        if skeleton_bvh_path:
            self.bvh_reader = self._create_bvh_reader(skeleton_bvh_path)
            self.pose = self.bvh_reader.get_hierarchy().create_pose()
        else:
            self.bvh_reader = None
            self.pose = None

        if self.args.train or self.needs_training_data():
            training_data_bvh_path = self._get_training_data_bvh_path()
            if training_data_bvh_path:
                if training_data_bvh_path == skeleton_bvh_path:
                    self.training_data_bvh_reader = self.bvh_reader
                else:
                    self.training_data_bvh_reader = self._create_bvh_reader(
                        training_data_bvh_path,
                        read_frames=self.should_read_bvh_frames())
            else:
                self.training_data_bvh_reader = self.bvh_reader
            self.training_entity = self.entity_class(
                self.training_data_bvh_reader, self.pose, self.args.floor, self.args.z_up, self.args)

        if self.bvh_reader:
            self.bvh_writer = BvhWriter(self.bvh_reader.get_hierarchy(), self.bvh_reader.get_frame_time())
                 
        self.input = None
        self.output = None
        self.entity = self.entity_class(self.bvh_reader, self.pose, self.args.floor, self.args.z_up, self.args)
        self._running = not args.stopped
        self.stopwatch = Stopwatch()
        if self.args.show_fps:
            self._fps_meter = FpsMeter()
        self.now = None
        self._frame_count = 0
        self._ui_handlers = set()
        self._ui_handlers_lock = threading.Lock()
        self._exporting_output = False

        if args.output_receiver_host:
            from connectivity import avatar_osc_sender
            if args.output_receiver_type == "world":
                self._output_sender = avatar_osc_sender.AvatarOscWorldSender(
                    args.output_receiver_port, args.output_receiver_host)
            elif args.output_receiver_type == "bvh":
                self._output_sender = avatar_osc_sender.AvatarOscBvhSender(
                    args.output_receiver_port, args.output_receiver_host)
        else:
            self._output_sender = None
            
        if self.args.entity == "hierarchical" and self.args.friction:
            self._enable_friction = True
            
        if args.receive_from_pn:
            self._pn_receiver = tracking.pn.receiver.PnReceiver()
            print "connecting to PN server..."
            self._pn_receiver.connect(args.pn_host, args.pn_port)
            print "ok"
            pn_pose = self.bvh_reader.get_hierarchy().create_pose()
            self._pn_entity = self.entity_class(self.bvh_reader, pn_pose, self.args.floor, self.args.z_up, self.args)
            self._input_from_pn = None
            pn_receiver_thread = threading.Thread(target=self._receive_from_pn)
            pn_receiver_thread.daemon = True
            pn_receiver_thread.start()

    def needs_training_data(self):
        return False
    
    def _get_skeleton_bvh_path(self):
        if self.args.bvh:
            if self.args.skeleton:
                raise Exception("Cannot provide both -bvh and -skeleton")
            return self.args.bvh
        return self.args.skeleton

    def _get_training_data_bvh_path(self):
        if self.args.bvh:
            if self.args.training_data:
                raise Exception("Cannot provide both -bvh and -training-data")
            return self.args.bvh
        return self.args.training_data

    def _create_bvh_reader(self, pattern, read_frames=True):
        bvh_filenames = glob.glob(pattern)
        if len(bvh_filenames) == 0:
            raise Exception("no files found matching the pattern %s" % pattern)
        print "loading BVHs from %s..." % pattern
        bvh_reader = BvhCollection(bvh_filenames)
        bvh_reader.read(read_frames=read_frames)
        print "ok"
        return bvh_reader
        
    def _save_student(self, event):
        filename = event.content
        print "saving %s..." % filename
        self.student.save(filename)
        print "ok"

    def _load_student(self, event):
        filename = event.content
        print "loading %s..." % filename
        self.student.load(filename)
        print "ok"

    def set_friction(self, enabled, inform_ui=False):
        if enabled != self._enable_friction:
            self._enable_friction = enabled
            self.entity.set_friction(enabled)
            if self.args.enable_io_blending:
                self._io_blending_entity.set_friction(enabled)
            if inform_ui:
                self.send_event_to_ui(Event(Event.SET_FRICTION, enabled))
        
    def add_parser_arguments_second_pass(self, parser, args):
        pass

    def ui_connected(self, handler):
        with self._ui_handlers_lock:
            self._ui_handlers.add(handler)
        if self.entity.processed_input is not None:
            self.send_event_to_ui(Event(Event.INPUT, self.entity.processed_input))
        if self.output is not None:
            self.process_and_broadcast_output()
        self.send_event_to_ui(Event(Event.FRAME_COUNT, self._frame_count))

    def ui_disconnected(self, handler):
        with self._ui_handlers_lock:
            if handler in self._ui_handlers:
                self._ui_handlers.remove(handler)

    def update_cursor(self, cursor):
        self.entity.set_cursor(cursor)

    def add_ui_parser_arguments(self, parser):
        from ui.ui import MainWindow
        MainWindow.add_parser_arguments(parser)

    def run_backend_and_or_ui(self):
        if self.args.start_frame is not None:
            print "fast-forwarding to frame %d..." % self.args.start_frame
            self.time_increment = 1. / self.args.frame_rate
            for n in range(self.args.start_frame):
                self._proceed_and_update()
            print "ok"
        else:
            self.entity.update(self.input)
            self.update()
                
        run_backend = not self.args.ui_only
        run_ui = not self.args.backend_only

        if run_ui:
            self._scene_class = self._entity_scene_module.Scene

        if self.args.with_profiler:
            import yappi
            yappi.start()

        if run_backend and run_ui:
            if self.args.websockets:
                websocket_server = self._create_websocket_server()
                self._start_in_new_thread(websocket_server)

            self._server = self._create_single_process_server()
            self._set_up_timed_refresh()
            self._start_in_new_thread(self._server)
            client = SingleProcessClient(self._server)
            self.run_ui(client)
        elif run_backend:
            self._server = self._create_websocket_server()
            self._set_up_timed_refresh()
            try:
                self._server.start()
            except KeyboardInterrupt:
                pass
        elif run_ui:
            if self.args.no_websockets:
                client = None
            else:
                client = WebsocketClient(self.args.backend_host)
            self.run_ui(client)

        if self.args.with_profiler:
            yappi.get_func_stats().print_all()

    def _start(self, event):
        self._running = True

    def _stop(self, event):
        self._running = False

    def is_running(self):
        return self._running

    def update(self):
        pass

    def _update_and_refresh_uis(self):
        if self.now is None:
            self.now = 0
            self.stopwatch.start()
        else:
            self.now = self.current_time()
            if self.is_running():
                if self.args.deterministic:
                    self.time_increment = 1. / self.args.frame_rate
                else:
                    self.time_increment = self.now - self.previous_frame_time
                if self.args.show_fps:
                    self._fps_meter.update()

                self._proceed_and_update()

                if self.entity.processed_input is not None:
                    self.send_event_to_ui(Event(Event.INPUT, self.entity.processed_input))

                if self.output is not None:
                    self.process_and_broadcast_output()

        self.previous_frame_time = self.now

        if self._exporting_output:
            self._export_bvh()
        if self._output_sender:
            self._send_output()

    def _proceed_and_update(self):
        self.proceed()
        self.entity.update(self.input)
        self.update()
        self._frame_count += 1
        self.send_event_to_ui(Event(Event.FRAME_COUNT, self._frame_count))
            
    def process_and_broadcast_output(self):
        if (self._server.client_subscribes_to(Event.OUTPUT) or
            self._output_sender and self.args.output_receiver_type == "world"):
            self.processed_output = self.entity.process_output(self.output)
            self.send_event_to_ui(Event(Event.OUTPUT, self.processed_output))

    def _proceed_to_next_frame(self, event):
        self.time_increment = 1. / self.args.frame_rate
        self._proceed_and_update()

        if self.output is not None:
            self.process_and_broadcast_output()
        if self.entity.processed_input is not None:
            self.send_event_to_ui(Event(Event.INPUT, self.entity.processed_input))

    def send_event_to_ui(self, event):
        with self._ui_handlers_lock:
            for ui_handler in self._ui_handlers:
                if not (event.source == "PythonUI" and ui_handler.__class__ == SingleProcessUiHandler):
                    ui_handler.send_event(event)

    def current_time(self):
        return self.stopwatch.get_elapsed_time()

    def _training_duration(self):
        if self.args.training_duration:
            return self.args.training_duration
        elif hasattr(self.training_entity, "get_duration"):
            return self.training_entity.get_duration()
        else:
            raise Exception(
                "training duration specified in neither arguments nor the %s class" % \
                    self.training_entity.__class__.__name__)

    def _create_single_process_server(self):
        return SingleProcessServer(SingleProcessUiHandler, experiment=self)

    def _create_websocket_server(self):
        server = WebsocketServer(WebsocketUiHandler, {"experiment": self})
        print "websocket server ready"
        self._invoke_potential_launcher_in_args()
        return server

    def _invoke_potential_launcher_in_args(self):
        if self.args.launch_when_ready:
            print "launching %r" % self.args.launch_when_ready
            self._launched_process = subprocess.Popen(self.args.launch_when_ready, shell=True)

    def _set_up_timed_refresh(self):
        self._server.add_periodic_callback(
            self._update_and_refresh_uis, 1000. / self.args.frame_rate)

    def _start_in_new_thread(self, server):
        server_thread = threading.Thread(target=server.start)
        server_thread.daemon = True
        server_thread.start()

    def _start_export_bvh(self, event):
        print "exporting BVH"
        self._exporting_output = True

    def _stop_export_bvh(self, event):
        if not os.path.exists(self.args.export_dir):
            os.mkdir(self.args.export_dir)
        export_path = self._get_export_path()
        print "saving export to %s" % export_path
        self.bvh_writer.write(export_path)
        self._exporting_output = False

    def _get_export_path(self):
        i = 1
        while True:
            path = "%s/export%03d.bvh" % (self.args.export_dir, i)
            if not os.path.exists(path):
                return path
            i += 1

    def _export_bvh(self):
        if self.output is not None:
            self.entity.parameters_to_processed_pose(self.output, self.pose)
            self.bvh_writer.add_pose_as_frame(self.pose)

    def _send_output(self):
        if self.output is not None:
            avatar_index = 0
            self._output_sender.send_frame(avatar_index, self.output, self.entity)

    def _receive_from_pn(self):
        for frame in self._pn_receiver.get_frames():
            self._input_from_pn = self._pn_entity.get_value_from_frame(frame)

    def _set_model_noise_to_add(self, event):
        self.model_noise_to_add = event.content / 100

    def _set_min_training_loss(self, event):
        self.min_training_loss = 0
        
class SingleProcessUiHandler:
    def __init__(self, client, experiment):
        self._client = client
        self._experiment = experiment
        self._experiment.ui_connected(self)

    def send_event(self, event):
        event.source = self
        self._client.received_event(event)

    def received_event(self, event):
        self._experiment.handle_event(event)
                      
class WebsocketUiHandler(ClientHandler):
    def __init__(self, *args, **kwargs):
        print "UI connected"
        self._experiment = kwargs.pop("experiment")
        super(WebsocketUiHandler, self).__init__(*args, **kwargs)

    def registered(self):
        print "UI registered"
        self._experiment.ui_connected(self)

    def on_close(self):
        print "UI disconnected"
        super(WebsocketUiHandler, self).on_close()
        self._experiment.ui_disconnected(self)

    def received_event(self, event, source):
        event.source = source
        self._experiment.handle_event(event)
