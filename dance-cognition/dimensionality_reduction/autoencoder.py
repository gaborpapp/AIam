from dimensionality_reduction import DimensionalityReduction
import numpy as np
import tensorflow as tf
import math
import random

class AutoEncoder(DimensionalityReduction):
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("--learning-rate", type=float, default=0.1)
        parser.add_argument("--num-hidden-nodes", type=int, default=3)
        parser.add_argument("--num-training-epochs", type=int, default=1000)

    def __init__(self, num_input_dimensions, num_reduced_dimensions, args):
        DimensionalityReduction.__init__(self, num_input_dimensions, num_reduced_dimensions, args)
        self._sess = tf.Session()
        self._create_layers(self.num_input_dimensions)
        self._saver = tf.train.Saver()
        init = tf.initialize_all_variables()
        self._sess.run(init)
        self._train_step = tf.train.GradientDescentOptimizer(self.args.learning_rate).minimize(self._cost)

    def train(self, training_data, num_training_epochs):
        try:
            for i in range(num_training_epochs):
                # training_datum = [random.choice(training_data)]
                # self._sess.run(self._train_step, feed_dict={self._input_layer: training_data})
                loss, _ = self._sess.run(
                    [self._cost, self._train_step], feed_dict={self._input_layer: training_data})
                print i, loss
        except KeyboardInterrupt:
            print "Training stopped at epoch %d" % i
            
    def _create_layers(self, num_input_dimensions):
        self._input_layer = tf.placeholder("float", [None, num_input_dimensions])
        # Build the encoding layers
        next_layer_input = self._input_layer

        encoding_matrices = []
        if self.args.num_hidden_nodes > 0:
            layer_sizes = [self.args.num_hidden_nodes, self.num_reduced_dimensions]
        else:
            layer_sizes = [self.num_reduced_dimensions]
        for dim in layer_sizes:
            input_dim = int(next_layer_input.get_shape()[1])

            # Initialize W using random values in interval [-1/sqrt(n) , 1/sqrt(n)]
            W = tf.Variable(tf.random_uniform([input_dim, dim], -1.0 / math.sqrt(input_dim), 1.0 / math.sqrt(input_dim)))

            # Initialize b to zero
            b = tf.Variable(tf.zeros([dim]))

            # We are going to use tied-weights so store the W matrix for later reference.
            encoding_matrices.append(W)

            output = tf.matmul(next_layer_input,W) + b

            # the input into the next layer is the output of this layer
            next_layer_input = output

        # The fully encoded x value is now stored in the next_layer_input
        self._encoded_x = next_layer_input

        # build the reconstruction layers by reversing the reductions
        layer_sizes.reverse()
        encoding_matrices.reverse()

        for i, dim in enumerate(layer_sizes[1:] + [ int(self._input_layer.get_shape()[1])]) :
            # we are using tied weights, so just lookup the encoding matrix for this step and transpose it
            W = tf.transpose(encoding_matrices[i])
            b = tf.Variable(tf.zeros([dim]))
            output = tf.nn.tanh(tf.matmul(next_layer_input,W) + b)
            next_layer_input = output

        # the fully encoded and reconstructed value of input_layer is here:
        self._reconstructed_input = next_layer_input

        self._cost = tf.sqrt(tf.reduce_mean(tf.square(self._input_layer-self._reconstructed_input)))
        
    def transform(self, observations):
        return self._sess.run(self._encoded_x, feed_dict={self._input_layer: observations})

    def inverse_transform(self, reductions):
        return self._sess.run(self._reconstructed_input, feed_dict={self._encoded_x: reductions})
    
    def save_model(self, path):
        self._saver.save(self._sess, path)

    def load_model(self, path):
        self._saver.restore(self._sess, path)
        
