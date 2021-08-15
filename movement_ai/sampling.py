import numpy
import sklearn.cluster
import sklearn.neighbors

class Sampler:
    @staticmethod
    def add_parser_arguments(parser):
        pass

    def __init__(self, observations, args):
        self._observations = observations
        self._args = args

class NoneSampler(Sampler):
    def sample(self):
        return self._observations

class NeighborhoodSampler(Sampler):
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("--num-neighborhoods", type=int, default=100)
        parser.add_argument("--samples-per-neighborhood", type=int, default=10)
        parser.add_argument("--neighborhood-size", type=int, default=0.1)

    def sample(self):
        num_inputs = len(self._observations)
        result = []
        for n in range(self._args.num_neighborhoods):
            observation_index = int(float(n) / self._args.num_neighborhoods * num_inputs)
            observation = self._observations[observation_index]
            result += self._sample_neighborhood(observation)
        return result

    def _sample_neighborhood(self, observation):
        num_dimensions = len(observation)
        return [observation + self._random_vector(num_dimensions,
                                                  magnitude=self._args.neighborhood_size)
                for n in range(self._args.num_samples)]

    def _random_vector(self, num_dimensions, magnitude):
        return (numpy.random.rand(num_dimensions) - 0.5) * magnitude

class KMeansSampler(Sampler):
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("--num-samples", type=int, default=500)

    def sample(self):
        kmeans = sklearn.cluster.KMeans(n_clusters=self._args.num_samples)
        kmeans.fit(self._observations)
        return kmeans.cluster_centers_

class MiniBatchKMeansSampler(Sampler):
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("--num-samples", type=int, default=500)

    def sample(self):
        kmeans = sklearn.cluster.MiniBatchKMeans(n_clusters=self._args.num_samples)
        kmeans.fit(self._observations)
        return kmeans.cluster_centers_

class DistanceDistributionEqualizationSampler(Sampler):
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("--num-samples", type=int, default=500)

    def sample(self):
        self._knn = sklearn.neighbors.KNeighborsClassifier(n_neighbors=2)
        indices = list(range(len(self._observations)))
        self._knn.fit(self._observations, indices)
        indices_sorted_by_nearest_neighbor_distance = sorted(
            indices,
            key=lambda index: self._distance_to_nearest_neighbor(index))
        linear_index_distribution = [
            int(n) for n in numpy.arange(
                0, len(self._observations), float(len(self._observations))/self._args.num_samples)]
        sampled_indices = [
            indices_sorted_by_nearest_neighbor_distance[index]
            for index in linear_index_distribution]
        return [self._observations[index] for index in sampled_indices]

    def _distance_to_nearest_neighbor(self, index):
        observation = self._observations[index]
        distances_list, _ = self._knn.kneighbors(observation, return_distance=True)
        distances = distances_list[0]
        return max(distances)

class MinDistanceSampler(Sampler):
    @staticmethod
    def add_parser_arguments(parser):
        parser.add_argument("--min-distance", type=float)
        parser.add_argument("--num-neighbors_ratio", type=float, default=0.01)

    def sample(self):
        knn = sklearn.neighbors.KNeighborsClassifier(
            n_neighbors=int(len(self._observations) * self._args.num_neighbors_ratio))
        indices = list(range(len(self._observations)))
        knn.fit(self._observations, indices)
        dropped_indices = set()
        for index, observation in zip(indices, self._observations):
            distances_list, neighbor_indices_list = knn.kneighbors(observation)
            distances = distances_list[0]
            neighbor_indices = neighbor_indices_list[0]
            for neighbor_index, distance in zip(neighbor_indices, distances):
                if (neighbor_index != index and
                    distance < self._args.min_distance and
                    neighbor_index not in dropped_indices):
                    dropped_indices.add(index)
                    break
        sampled_indices = set(indices) - dropped_indices
        return [self._observations[index] for index in sampled_indices]
