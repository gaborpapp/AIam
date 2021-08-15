from argparse import ArgumentParser

from . import pca
from .autoencoder import AutoEncoder

class DimensionalityReductionFactory:
    TYPES = ["LinearPCA", "KernelPCA", "AutoEncoder"]

    @staticmethod
    def get_class(type_name):
        if type_name == "LinearPCA":
            return pca.LinearPCA
        elif type_name == "KernelPCA":
            return pca.KernelPCA
        elif type_name == "AutoEncoder":
            return AutoEncoder

    @staticmethod
    def create(type_name, num_input_dimensions, num_reduced_dimensions, args_string):
        cls = DimensionalityReductionFactory.get_class(type_name)
        parser = ArgumentParser()
        cls.add_parser_arguments(parser)
        args_strings = args_string.split()
        args = parser.parse_args(args_strings)
        return cls(num_input_dimensions, num_reduced_dimensions, args)
    
