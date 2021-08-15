from .dimensionality_reduction import DimensionalityReduction
import sklearn.decomposition
import pickle

class PCADimensionalityReduction(DimensionalityReduction):
    def fit(self, *args, **kwargs):
        return self.pca.fit(*args, **kwargs)

    def transform(self, *args, **kwargs):
        return self.pca.transform(*args, **kwargs)
        
    def fit_transform(self, *args, **kwargs):
        return self.pca.fit_transform(*args, **kwargs)

    def inverse_transform(self, *args, **kwargs):
        return self.pca.inverse_transform(*args, **kwargs)
        
    def save_model(self, path):
        f = open(path, "wb")
        pickle.dump(self.pca, f)
        f.close()

    def load_model(self, path):
        f = open(path, "rb")
        self.pca = pickle.load(f)
        f.close()
        
class LinearPCA(PCADimensionalityReduction):
    def __init__(self, num_input_dimensions, num_reduced_dimensions, args):
        DimensionalityReduction.__init__(self, num_input_dimensions, num_reduced_dimensions, args)
        self.pca = sklearn.decomposition.PCA(n_components=num_reduced_dimensions)

    def analyze_accuracy(self, observations):
        print("explained variance ratio: %s (sum %s)" % (
            self.pca.explained_variance_ratio_, sum(self.pca.explained_variance_ratio_)))
        DimensionalityReduction.analyze_accuracy(self, observations)

class KernelPCA(PCADimensionalityReduction):
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("--pca-kernel", default="poly")

    def __init__(self, num_input_dimensions, num_reduced_dimensions, args):
        DimensionalityReduction.__init__(self, num_input_dimensions, num_reduced_dimensions, args)
        self.pca = sklearn.decomposition.KernelPCA(
            n_components=num_reduced_dimensions,
            kernel=args.pca_kernel, fit_inverse_transform=True, gamma=0.5)
