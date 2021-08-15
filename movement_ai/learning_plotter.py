class LearningPlotter:
    def __init__(self, student, teacher, duration):
        self._student = student
        self._teacher = teacher
        self._duration = duration

    def plot(self, filename):
        f = open(filename, "w")
        t = 0
        time_increment = 1.0 / 50
        while t < self._duration:
            if self._teacher.collected_enough_training_data():
                inp = self._teacher.get_input()
                expected_output = self._teacher.get_output()
                self._student.train(inp, expected_output)
                output = self._student.process(inp)
                error = self._teacher.judge_error(expected_output, output)
                print(t, error, file=f)
            self._teacher.proceed(time_increment)
            t += time_increment
        f.close()
