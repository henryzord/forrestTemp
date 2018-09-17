import os
from collections import Counter
# noinspection PyUnresolvedReferences
from cpu_device import make_predictions

import numpy as np
import pandas as pd
from termcolor import colored


class Device(object):
    def __init__(self, dataset):
        """

        :type dataset: pandas.DataFrame
        :param dataset:
        """

        cur_path = os.path.abspath(__file__)
        self._split = os.sep.join(cur_path.split(os.sep)[:-1])

        self.dataset = dataset
        self.dataset[self.dataset.columns[-1]] = pd.Categorical(self.dataset[self.dataset.columns[-1]])
        self.dataset[self.dataset.columns[-1]] = self.dataset[self.dataset.columns[-1]].cat.codes

    def predict(self, data, dt):
        """

        Makes predictions for unseen samples.

        :param data:
        :type dt: individual.DecisionTree
        :param dt:
        :rtype: pandas.DataFrame
        :return:
        """

        tree = dt.tree._node

        shape = None
        if isinstance(data, pd.DataFrame):
            shape = data.shape
            data = data.values.ravel().tolist()
        elif isinstance(data, np.ndarray):
            shape = data.shape
            data = data.ravel().tolist()
        elif isinstance(data, list):
            n_instances = len(data)
            n_attributes = len(data[0])
            shape = (n_instances, n_attributes)
            data = np.array(data).ravel().tolist()  # removes extra dimensions

        preds = make_predictions(
            shape,  # shape of sample data
            data,  # dataset as a plain list
            tree,  # tree in dictionary format
            list(range(shape[0])),  # shape of prediction array
            self.dataset_info.attribute_index  # dictionary where keys are attributes and values their indices
        )

        raise NotImplementedError('not returning correct values!')

        return preds

    @staticmethod
    def entropy(subset):
        """
        The smaller, the purer.
        Class attribute must be the last attribute.

        :type subset: pandas.DataFrame
        :param subset:
        :rtype: float
        :return: The entropy for the provided subset.
        """
        size = len(subset)

        counter = Counter(subset[subset.columns[-1]])

        _entropy = 0.

        for i, (c, q) in enumerate(counter.items()):
            _entropy += (q / float(size)) * np.log2(q / float(size))

        return -1. * _entropy

    @staticmethod
    def __split_info__(subset, subset_left, subset_right):
        split_info = 0.
        for child_subset in [subset_left, subset_right]:
            if child_subset.shape[0] <= 0 or subset.shape[0] <= 0:
                pass
            else:
                share = (child_subset.shape[0] / float(subset.shape[0]))
                split_info += share * np.log2(share)

        return -split_info

    @staticmethod
    def information_gain(subset, subset_left, subset_right):
        sum_term = 0.
        n_objects = len(subset)

        subset_entropy = Device.entropy(subset)

        for child_subset in [subset_left, subset_right]:
            n_objects_subset = len(child_subset)
            child_entropy = Device.entropy(child_subset)
            sum_term += (float(n_objects_subset) / n_objects) * child_entropy

        ig = subset_entropy - sum_term

        # print("((%.3d/%.3d) * -%.3f) + ((%.3d/%.3d) * -%.3f)" % (len(subset_left), len(subset), Device.entropy(subset_left), len(subset_right), len(subset), Device.entropy(subset_right)))

        return ig

    @staticmethod
    def gain_ratio(subset, subset_left, subset_right):
        ig = Device.information_gain(subset, subset_left, subset_right)
        si = Device.__split_info__(subset, subset_left, subset_right)

        if ig > 0. and si > 0.:
            gr = ig / si
        else:
            gr = 0.

        return gr

    @staticmethod
    def get_gain_ratios(dataset, subset_index, attribute, candidates):
        """
        Method for getting several gain ratios, based on several threshold values.

        :param dataset:
        :type dataset: pandas.DataFrame
        :param subset_index:
        :param attribute: Name of the attribute.
        :type attribute: str
        :param candidates: Candidate values.
        :return:
        """

        proper_subset = dataset.loc[subset_index.astype(np.bool)]

        ratios = np.empty(len(candidates), dtype=np.float32)
        for i, candidate in enumerate(candidates):
            subset_left = proper_subset.loc[proper_subset[attribute] <= candidate]
            subset_right = proper_subset.loc[proper_subset[attribute] > candidate]

            ratios[i] = Device.gain_ratio(proper_subset, subset_left, subset_right)
        return ratios


try:
    # noinspection PyUnresolvedReferences
    import pyopencl
    from opencl import CLDevice as AvailableDevice
    print(colored('NOTICE: Using OpenCL as device.', 'yellow'))
except ImportError:
    AvailableDevice = Device
    print(colored('NOTICE: Using single-threaded CPU as device.', 'yellow'))

# from termcolor import colored
# from __base__ import  Device as AvailableDevice
# print colored('NOTICE: Using single-threaded CPU as device.', 'yellow')
