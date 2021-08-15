from stopwatch import Stopwatch
import collections

class FpsMeter:
    print_fps = True
    
    def __init__(self, name=None):
        if name is None:
            self._name_argument_string = ""
        else:
            self._name_argument_string = "(%s)" % name
        self._fps_history = collections.deque(maxlen=10)
        self._previous_time = None
        self._previous_calculated_fps_time = None
        self._stopwatch = Stopwatch()
        self._fps = None

    def update(self):
        self._now = self._stopwatch.get_elapsed_time()
        if self._previous_time is None:
            self._stopwatch.start()
        else:
            self._update_fps_history()
            self._update_fps_if_timely()
        self._previous_time = self._now

    def _update_fps_history(self):
        time_increment = self._now - self._previous_time
        fps = 1.0 / time_increment
        self._fps_history.append(fps)

    def _update_fps_if_timely(self):
        if self._previous_calculated_fps_time:
            if (self._stopwatch.get_elapsed_time() - self._previous_calculated_fps_time) > 1.0:
                self._calculate_fps()
        else:
            self._calculate_fps()

    def _calculate_fps(self):
        self._fps = sum(self._fps_history) / len(self._fps_history)
        if self.print_fps:
            print("FPS%s: %.1f" % (self._name_argument_string, self._fps))
        self._previous_calculated_fps_time = self._stopwatch.get_elapsed_time()

    def get_fps(self):
        return self._fps
    
