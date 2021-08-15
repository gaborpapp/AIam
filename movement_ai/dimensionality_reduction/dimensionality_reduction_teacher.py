import numpy

class Teacher:
    def __init__(self, stimulus, frame_rate):
        self._stimulus = stimulus
        self._frame_rate = frame_rate

    def create_training_data(self, duration):
        print("creating training data for %.1fs with %.1f FPS..." % (duration, self._frame_rate))
        self._training_data = []
        time_increment = 1.0 / self._frame_rate
        t = 0
        while t < duration:
            self._add_training_datum()
            self.proceed(time_increment)
            t += time_increment
        print("created training data with %s samples" % len(self._training_data))
        return numpy.array(self._training_data)

    def proceed(self, time_increment):
        self._stimulus.proceed(time_increment)

    def _add_training_datum(self):
        datum = list(self._stimulus.get_value())
        self._training_data.append(datum)
