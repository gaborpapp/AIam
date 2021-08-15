import numpy

class ComponentAnalysis:
    def __init__(self, pca, num_output_components, parameter_info_getter):
        self._pca = pca
        self._parameter_info_getter = parameter_info_getter
        self._num_output_components = num_output_components

    def analyze(self):
        for n in range(self._pca.num_reduced_dimensions):
            self._analyze_component(n)

    def _analyze_component(self, n, resolution=10, group_by_parameter_category=True):
        print("component %s:" % n)

        output_components = []
        for output_component_index in range(self._num_output_components):
            parameter_info = self._parameter_info_getter(output_component_index)
            output_components.append({"parameter_category": parameter_info["category"],
                                      "parameter_components": [parameter_info["component"]],
                                      "variance": 0.})

        for normalized_reduction in self._pca.normalized_observed_reductions:
            reconstructions = []
            for x in numpy.arange(0., 1., 1./resolution):
                normalized_reduction[n] = x
                reduction = self._pca.unnormalize_reduction(normalized_reduction)
                reconstruction = self._pca.inverse_transform(reduction)[0]
                reconstructions.append(reconstruction)
            reconstructions = numpy.array(reconstructions)

            for output_component_index in range(self._num_output_components):
                variance = numpy.var(reconstructions[:,output_component_index])
                output_components[output_component_index]["variance"] += variance

        if group_by_parameter_category:
            output_components = self._group_components_by_category(output_components)
        output_components_sorted_by_variance = sorted(
            output_components,
            key=lambda output_component: -output_component["variance"])
        for i in range(10):
            output_component = output_components_sorted_by_variance[i]
            print("  %s [%s] (%s)" % (
                output_component["parameter_category"],
                ",".join(output_component["parameter_components"]),
                output_component["variance"]))

    def _group_components_by_category(self, components):
        result = []
        for component in components:
            self._add_component_to_result(component, result)
        return result

    def _add_component_to_result(self, component, result):
        for other in result:
            if other["parameter_category"] == component["parameter_category"]:
                other["parameter_components"].extend(component["parameter_components"])
                other["variance"] += component["variance"]
                return result
        result.append(component)
        return result
