import time
import pickle
import os
import threading

class EventListener:
    def __init__(self, handlers={}):
        self._handlers = handlers
        self._writing_events_to_log = False

    def handle_event(self, event):
        if self._writing_events_to_log:
            self._log_event(event)
        try:
            handler = self._handlers[event.type]
        except KeyError:
            raise Exception("Unknown event type %r. Handlers added for %r." % (
                    event.type, list(self._handlers.keys())))
        handler(event)

    def get_handled_events(self):
        return list(self._handlers.keys())

    def set_event_log_target(self, filename):
        self._writing_events_to_log = True
        if os.path.exists(filename):
            raise Exception("event log target %r already exists" % filename)
        self._event_log_target_file = open(filename, "w")

    def _log_event(self, event):
        self._event_log_target_file.write(self._serialize((time.time(), event)))

    def _serialize(self, obj):
        try:
            return pickle.dumps(obj)
        except Exception as exception:
            raise Exception("failed to serialize %s: %s" % (obj, exception))

    def set_event_log_source(self, filename):
        self._read_event_log(filename)
        self._reading_events_from_log = True
        self._current_event_log_time = None

    def _read_event_log(self, filename):
        print("reading event log file %s..." % filename)
        f = open(filename, "r")
        self._event_log_entries = []
        try:
            while True:
                entry = self._unserialize_from_file(f)
                self._event_log_entries.append(entry)
        except EOFError:
            pass
        f.close()
        print("ok")

    def _unserialize_from_file(self, f):
        return pickle.load(f)

    def process_event_log_in_new_thread(self):
        thread = threading.Thread(name="process_log", target=self._process_event_log)
        thread.daemon = True
        thread.start()

    def _process_event_log(self):
        while True:
            if len(self._event_log_entries) == 0:
                print("finished processing log")
                return
            t, event = self._event_log_entries.pop(0)
            if self._current_event_log_time is None:
                self._current_event_log_time = t
            else:
                self._sleep_until(t)
            self.received_event(event)

    def _sleep_until(self, t, max_sleep_duration=1.0):
        while self._current_event_log_time < t:
            sleep_duration = min(t - self._current_event_log_time, max_sleep_duration)
            time.sleep(sleep_duration)
            self._current_event_log_time += sleep_duration
