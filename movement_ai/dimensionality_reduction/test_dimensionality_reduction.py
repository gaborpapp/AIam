import numpy as np
import matplotlib.pyplot as plt
import random
from .pca import *
import argparse
import tensorflow as tf
import math

num_input_dimensions = 2
num_reduced_dimensions = 1
num_hidden_nodes = 3

def create(input_layer, layer_sizes):

	# Build the encoding layers
	next_layer_input = input_layer

	encoding_matrices = []
	for dim in layer_sizes:
		input_dim = int(next_layer_input.get_shape()[1])

		# Initialize W using random values in interval [-1/sqrt(n) , 1/sqrt(n)]
		W = tf.Variable(tf.random_uniform([input_dim, dim], -1.0 / math.sqrt(input_dim), 1.0 / math.sqrt(input_dim)))

		# Initialize b to zero
		b = tf.Variable(tf.zeros([dim]))

		# We are going to use tied-weights so store the W matrix for later reference.
		encoding_matrices.append(W)

		output = tf.nn.tanh(tf.matmul(next_layer_input,W) + b)

		# the input into the next layer is the output of this layer
		next_layer_input = output

	# The fully encoded x value is now stored in the next_layer_input
	encoded_x = next_layer_input

	# build the reconstruction layers by reversing the reductions
	layer_sizes.reverse()
	encoding_matrices.reverse()


	for i, dim in enumerate(layer_sizes[1:] + [ int(input_layer.get_shape()[1])]) :
		# we are using tied weights, so just lookup the encoding matrix for this step and transpose it
		W = tf.transpose(encoding_matrices[i])
		b = tf.Variable(tf.zeros([dim]))
		output = tf.nn.tanh(tf.matmul(next_layer_input,W) + b)
		next_layer_input = output

	# the fully encoded and reconstructed value of input_layer is here:
	reconstructed_input = next_layer_input

	return {
		'encoded': encoded_x,
		'decoded': reconstructed_input,
		'cost' : tf.sqrt(tf.reduce_mean(tf.square(input_layer-reconstructed_input)))
	}

parser = argparse.ArgumentParser()
parser.add_argument("type", choices=["pca", "nn"])
parser.add_argument("--pca-type", choices=["LinearPCA", "KernelPCA"], default="LinearPCA")
parser.add_argument("--batch-size", type=int, default=1000)
parser.add_argument("--num-training-epochs", type=int, default=1000)
parser.add_argument("--learning-rate", type=float, default=0.5)
parser.add_argument("--animate", action="store_true")
KernelPCA.add_parser_arguments(parser)
args = parser.parse_args()

   
def create_training_data(num_samples):
        training_data = []
        for j in range(num_samples):
            x = random.uniform(-1, 1)
            y = x*x
            vec = np.array([x, y])
            training_data.append(np.random.normal(vec, 0.1))
        training_data = np.array(training_data)
        return training_data

def plot(training_data, output_data):
        plot_colors = ["#ff8080"] * len(training_data) + ["#ff0000"] * len(output_data)
        plot_data = np.append(training_data, output_data, axis=0)
        plt.clf()
        plt.scatter(plot_data[:,0], plot_data[:,1], c=plot_colors, alpha=0.3)

if args.type == "pca":
        training_data = create_training_data(args.batch_size)
        if args.pca_type == "KernelPCA":
                pca = KernelPCA(num_reduced_dimensions=num_reduced_dimensions, args=args)
        elif args.pca_type == "LinearPCA":
                pca = LinearPCA(num_reduced_dimensions=num_reduced_dimensions, args=args)
        pca.fit(training_data)
        output_data = pca.inverse_transform(pca.transform(training_data))
        plot(training_data, output_data)
        plt.show()
        
elif args.type == "nn":
        sess = tf.Session()
        input_layer = tf.placeholder("float", [None, num_input_dimensions])
        if num_hidden_nodes > 0:
                layer_sizes = [num_hidden_nodes, num_reduced_dimensions]
        else:
                layer_sizes = [num_reduced_dimensions]
        autoencoder = create(input_layer, layer_sizes)
        init = tf.initialize_all_variables()
        sess.run(init)
        train_step = tf.train.GradientDescentOptimizer(args.learning_rate).minimize(autoencoder['cost'])

        if args.animate:
                for i in range(args.num_training_epochs):
                        training_data = create_training_data(1)
                        sess.run(train_step, feed_dict={input_layer: training_data})
                        test_data = create_training_data(args.batch_size)
                        loss, output_data = sess.run(
                                [autoencoder['cost'], autoencoder['decoded']],
                                feed_dict={input_layer: test_data})
                        plot(test_data, output_data)
                        plt.title('batch %d, loss %g' % (i, loss))
                        plt.show(False)
                        plt.pause(0.0001)
        else:
                for i in range(args.num_training_epochs):
                        training_data = create_training_data(1)
                        sess.run(train_step, feed_dict={input_layer: training_data})
                test_data = create_training_data(args.batch_size)
                loss, output_data = sess.run(
                        [autoencoder['cost'], autoencoder['decoded']],
                        feed_dict={input_layer: test_data})
                print("loss %g" % loss)
                plot(test_data, output_data)
                plt.show()

