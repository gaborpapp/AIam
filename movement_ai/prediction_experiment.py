from experiment import *
from backprop_net import BackpropNet
from prediction_teacher import *

class PredictionExperiment(Experiment):
    @staticmethod
    def add_parser_arguments(parser):
        Experiment.add_parser_arguments(parser)
        parser.add_argument("-shuffle-input", action="store_true")
        parser.add_argument("-plot", type=str)
        parser.add_argument("-plot-duration", type=float, default=10)

    def __init__(self, parser):
        self.profiles_dir = "profiles/prediction"
        Experiment.__init__(self, parser)

    def run(self):
        if self.args.shuffle_input:
            self.teacher = ShufflingTeacher(self.entity)
        else:
            self.teacher = LiveTeacher(self.entity)

        if self.args.train:
            num_parameters = len(self.entity.get_value())
            self.student = BackpropNet(
                num_parameters,
                num_parameters * 2,
                num_parameters)
            self._train_model()
            storage.save(self.student, self._student_model_path)

        else:
            self.student = storage.load(self._student_model_path)

            if self.args.plot:
                LearningPlotter(student, teacher, self.args.plot_duration).plot(self.args.plot)

            else:
                self.run_backend_and_or_ui()

    def run_ui(self, client):
        from ui.ui import MainWindow, ExperimentToolbar
        from PyQt4 import QtGui
        app = QtGui.QApplication(sys.argv)
        app.setWindowIcon(QtGui.QIcon("ui/icon.png"))
        window = MainWindow(client,
            self.entity, self.student, self.bvh_reader, self._scene_class, ExperimentToolbar, self.args)
        window.start()
        if client:
            client.connect()
        window.show()
        app.exec_()

    def proceed(self):
        if self.teacher.collected_enough_training_data():
            inp = self.teacher.get_input()
            expected_output = self.teacher.get_output()
            self.student.train(inp, expected_output)
        self.teacher.proceed(self.time_increment)

        self.input = self.entity.get_value()
        self.output = self.student.process(self.input)

    def _train_model(self):
        print("training model...")
        t = 0
        time_increment = 1.0 / 50
        training_duration = self._training_duration()
        while t < training_duration:
            if self.teacher.collected_enough_training_data():
                inp = self.teacher.get_input()
                output = self.teacher.get_output()
                self.student.train(inp, output)
            self.teacher.proceed(time_increment)
            t += time_increment
        print("ok")

    def should_read_bvh_frames(self):
        return True
