# Outputs data file which can be used e.g. with gnuplot.
#
# Example usage:
# gnuplot> plot "observations.dat" with points pointsize 0.5 pointtype 7 lc rgb "#a08080", "./samples.dat"  with points pointsize 1 pointtype 2 lc rgb "#0000ff"
#
# observations.dat can be generated with plot_observations.py

from dimensionality_reduction.dimensionality_reduction_experiment import *

parser = ArgumentParser()
parser.add_argument("--output", "-o", default="samples.dat")
parser.add_argument("--select-dimensions",
                    default="0,1",
                    help="e.g. 0,3 (x as 1st dimension and y as 4th)")

DimensionalityReductionExperiment.add_parser_arguments(parser)
experiment = DimensionalityReductionExperiment(parser)
experiment._load_model()

args = experiment.args
selected_dimensions = [int(string) for string in args.select_dimensions.split(",")]

data = experiment.student.normalized_observed_reductions[:,selected_dimensions]
samples = experiment._sampling_class(data, experiment._sampling_args).sample()

out = open(args.output, "w")
for sample in samples:
    print(" ".join([str(value) for value in sample]), file=out)
out.close()
