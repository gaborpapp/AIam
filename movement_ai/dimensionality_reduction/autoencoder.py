from dimensionality_reduction import DimensionalityReduction
import numpy as np
import tensorflow as tf
import math
import random
from backports import tempfile
from zipfile import ZipFile
import os
import collections

class AutoEncoder(DimensionalityReduction):
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("--learning-rate", type=float, default=0.1)
        parser.add_argument("--learning-rate-decay", type=float)
        parser.add_argument("--num-hidden-nodes", type=int, nargs="*")
        parser.add_argument("--num-training-epochs", type=int)
        parser.add_argument("--target-loss-slope", type=float)
        parser.add_argument("--tied-weights", action="store_true")
        parser.add_argument("--activation-function", choices=["tanh"])

    def __init__(self, num_input_dimensions, num_reduced_dimensions, args):
        DimensionalityReduction.__init__(self, num_input_dimensions, num_reduced_dimensions, args)
        self._graph = tf.Graph()
        with self._graph.as_default():
            self._sess = tf.Session()
            self._create_layers(self.num_input_dimensions)
            self._global_step = tf.Variable(0, trainable=False)
            self._saver = tf.train.Saver()
            self._set_up_logging()
            init = tf.initialize_all_variables()
            self._sess.run(init)
        self.set_learning_rate(self._get_learning_rate_from_args())

    def _get_learning_rate_from_args(self):
        if self.args.learning_rate_decay:
            return tf.train.exponential_decay(
                self.args.learning_rate, self._global_step, 1, self.args.learning_rate_decay)
        else:
            return self.args.learning_rate        
        
    def _set_up_logging(self):
        with tf.name_scope("summaries"):
            tf.summary.scalar("cost", self._cost)
        self._merged = tf.summary.merge_all()
        self._train_writer = tf.summary.FileWriter("logs/train", self._sess.graph)

    def get_learning_rate(self):
        return self._learning_rate
    
    def set_learning_rate(self, learning_rate):
        self._learning_rate = learning_rate
        with self._graph.as_default():
            self._train_step = tf.train.GradientDescentOptimizer(learning_rate).minimize(
                self._cost, global_step=self._global_step)

    def batch_train(self,
                    training_data,
                    num_training_epochs=None,
                    target_training_loss=None,
                    target_loss_slope=None):
        if target_loss_slope:
            loss_slope_history = collections.deque(maxlen=10)
            previous_loss = None
        epoch = 0
        with self._graph.as_default():
            try:
                while True:
                    loss, summary, _ = self._sess.run(
                        [self._cost, self._merged, self._train_step],
                        feed_dict={self._input_layer: training_data})
                    self._train_writer.add_summary(summary, epoch)
                    if num_training_epochs is not None and epoch >= num_training_epochs:
                        break
                    if target_training_loss and loss <= target_training_loss:
                        print "Stopping at epoch %d (loss %s <= %s)" % (
                            epoch, loss, target_training_loss)
                        break
                    if target_loss_slope:
                        if previous_loss is not None:
                            loss_slope = previous_loss - loss
                            loss_slope_history.append(loss_slope)
                            if len(loss_slope_history) == 10:
                                mean_loss_slope = sum(loss_slope_history) / len(loss_slope_history)
                                if 0 <= mean_loss_slope <= target_loss_slope:
                                    print "Stopping at epoch %d (loss slope: 0 <= %s <= %s)" % (
                                        epoch, mean_loss_slope, target_loss_slope)
                                    break
                        previous_loss = loss
                    epoch += 1
            except KeyboardInterrupt:
                print "Training stopped at epoch %d" % epoch

    def train(self, training_data, return_loss=False):
        with self._graph.as_default():
            if return_loss:
                loss, _ = self._sess.run(
                    [self._cost, self._train_step], feed_dict={self._input_layer: training_data})
                return loss
            else:
                self._sess.run(self._train_step, feed_dict={self._input_layer: training_data})
                
    def _create_layers(self, num_input_dimensions):
        self._input_layer = tf.placeholder("float", [None, num_input_dimensions])
        # Build the encoding layers
        next_layer_input = self._input_layer

        self._encoding_matrices = []
        self._weight_tensors = []
        if len(self.args.num_hidden_nodes) == 0 or self.args.num_hidden_nodes == [0]:
            self._layer_sizes = [self.num_reduced_dimensions]
        else:
            self._layer_sizes = self.args.num_hidden_nodes + [self.num_reduced_dimensions]
        for dim in self._layer_sizes:
            input_dim = int(next_layer_input.get_shape()[1])
            weight_tensor = self._random_weights(input_dim, dim)
            self._weight_tensors.append(weight_tensor)
            b = tf.Variable(tf.zeros([dim]))
            self._encoding_matrices.append(weight_tensor.variable)
            output = tf.matmul(next_layer_input, weight_tensor.variable) + b
            next_layer_input = output

        # The fully encoded x value is now stored in the next_layer_input
        self._encoded_x = next_layer_input

        # build the reconstruction layers by reversing the reductions
        self._layer_sizes.reverse()
        self._encoding_matrices.reverse()
        self._decoding_matrices = []

        for i, dim in enumerate(self._layer_sizes[1:] + [ int(self._input_layer.get_shape()[1])]) :
            input_dim = int(next_layer_input.get_shape()[1])
            if self.args.tied_weights:
                W = tf.transpose(self._encoding_matrices[i])
            else:
                weight_tensor = self._random_weights(input_dim, dim)
                W = weight_tensor.variable
                self._weight_tensors.append(weight_tensor)
            self._decoding_matrices.append(W)
            b = tf.Variable(tf.zeros([dim]))
            summed_inputs = tf.matmul(next_layer_input,W) + b
            if self.args.activation_function == "tanh":
                output = tf.nn.tanh(summed_inputs)
            else:
                output = summed_inputs
            next_layer_input = output

        # the fully encoded and reconstructed value of input_layer is here:
        self._reconstructed_input = next_layer_input

        self._cost = tf.sqrt(tf.reduce_mean(tf.square(self._input_layer-self._reconstructed_input)))

    def _random_weights(self, input_dim, output_dim):
        tensor = tf.random_uniform(
            [input_dim, output_dim],
            -1.0 / math.sqrt(input_dim),
            1.0 / math.sqrt(input_dim))
        return WeightTensor(tensor)

    def transform(self, observations):
        with self._graph.as_default():
            return self._sess.run(self._encoded_x, feed_dict={self._input_layer: observations})

    def inverse_transform(self, reductions):
        with self._graph.as_default():
            return self._sess.run(self._reconstructed_input, feed_dict={self._encoded_x: reductions})
    
    def save_model(self, path):
        with self._graph.as_default():
            with tempfile.TemporaryDirectory() as tempdir:
                self._saver.save(self._sess, "%s/model" % tempdir)
                with ZipFile(path, "w") as zipfile:
                    for root, dirs, files in os.walk(tempdir):
                        for filename in files:
                            zipfile.write(os.path.join(root, filename), filename)
        
    def load_model(self, path):
        with self._graph.as_default():
            with tempfile.TemporaryDirectory() as tempdir:
                zipfile = ZipFile(path, "r")
                zipfile.extractall(tempdir)
                self._saver.restore(self._sess, "%s/model" % tempdir)

    def supports_incremental_learning(self):
        return True
    
    def add_noise(self, amount):
        with self._graph.as_default():
            for weight_tensor in self._weight_tensors:
                op = weight_tensor.variable.assign_add(
                    tf.random_uniform(weight_tensor.variable.shape, -amount, amount),
                    use_locking=True)
                self._sess.run(op)

    def reset(self):
        for weight_tensor in self._weight_tensors:
            op = weight_tensor.variable.assign(weight_tensor.tensor)
            self._sess.run(op)

class WeightTensor:
    def __init__(self, tensor):
        self.tensor = tensor
        self.variable = tf.Variable(tensor)
