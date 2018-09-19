# coding=utf-8

import json
from collections import Counter

import networkx as nx
import pandas as pd
from sklearn.metrics import accuracy_score
import numpy as np
from cpu_device import gain_ratio
import copy

from utils import raw_type_dict, mid_type_dict

__author__ = 'Henry Cagnini'


class HeapTree(object):

    def __init__(self, max_depth=1):
        pass

    @staticmethod
    def get_node_count(depth):
        """
        Get number of total nodes from a tree with given depth.

        :param depth: Depth of binary tree.
        :type depth: int
        :rtype: int
        :return: The number of nodes in this tree.
        """
        return np.power(2, depth + 1) - 1

    @staticmethod
    def node_count_at(depth):
        """
        Get number of nodes at given level.

        :type depth: int
        :param depth: The querying depth. Starts at zero (i.e. root).
        :rtype: int
        :return: Number of nodes at queried depth.
        """

        return np.power(2, depth)

    @staticmethod
    def get_depth(id_node):
        """
        Gets depth of node in a binary heap.

        :param id_node: ID of the node in the binary heap.
        :return: The depth of the node.
        """
        return int(np.log2(id_node + 1))

    @staticmethod
    def get_left_child_id(id_node):
        return (id_node * 2) + 1

    @staticmethod
    def get_right_child_id(id_node):
        return (id_node * 2) + 2

    @staticmethod
    def get_parent_id(id_node):
        if id_node > 0:
            return int((id_node - 1) / 2.)
        return None


class DecisionTree(HeapTree):
    _terminal_node_color = '#98FB98'
    _inner_node_color = '#0099ff'
    _root_node_color = '#FFFFFF'

    initialized = False

    @classmethod
    def __set_class_values__(cls, max_depth, full_df, train_index, val_index):
        if not cls.initialized:
            cls.column_types = {x: mid_type_dict[raw_type_dict[str(full_df[x].dtype)]] for x in full_df.columns}

            cls.max_depth = max_depth
            cls.train_index = train_index
            cls.val_index = val_index

            cls.pred_attr_names = np.array(full_df.columns[:-1])  # type: np.ndarray

            cls.pred_attr_values = dict()
            for column in full_df.columns:
                if str(full_df[column].dtype) == 'category':
                    cls.pred_attr_values[column] = dict(zip(full_df[column].cat.codes, full_df[column].cat.categories))

            cls.class_attr_name = full_df.columns[-1]  # type: str
            cls.class_labels = np.sort(full_df[full_df.columns[-1]].unique())  # type: np.ndarray

            _attr_forward = {
                k: v for k, v in zip(full_df.columns, range(len(cls.pred_attr_names) + 1))
            }
            _attr_backward = {
                k: v for k, v in zip(range(len(cls.pred_attr_names) + 1), cls.pred_attr_names + [cls.class_attr_name])
            }

            _attr_forward.update(_attr_backward)
            cls.attr_index = _attr_forward

            _class_forward = {
                k: v for k, v in zip(cls.class_labels, range(len(cls.class_labels)))
            }
            _class_backward = {
                k: v for k, v in zip(range(len(cls.class_labels)), cls.class_labels)
            }

            _class_forward.update(_class_backward)
            cls.class_labels_index = _class_forward

            cls.full_df = cls.normalize_dataset(full_df)

            # since the probability of generating the class at D is 100%
            cls.n_nodes = cls.get_node_count(cls.max_depth - 1)

            cls.initialized = True

    def __init__(self, max_depth, full_df, train_index, val_index):
        """

        :param max_depth:
        :param full_df:
        :param train_index:
        :param val_index:
        """
        super(DecisionTree, self).__init__(max_depth=max_depth)

        self.__class__.__set_class_values__(
            max_depth=max_depth,
            full_df=full_df,
            train_index=train_index,
            val_index=val_index
        )

        longest_word = max(map(len, list(self.class_labels) + list(self.pred_attr_names) + [self.class_attr_name]))
        dtype = '<U%d' % longest_word

        self.nodes = np.empty(self.n_nodes, dtype=np.dtype(dtype))
        self.threshold = np.empty(self.n_nodes, dtype=np.float32)
        self.terminal = np.empty(self.n_nodes, dtype=np.bool)

    @staticmethod
    def normalize_dataset(dataset):
        """

        :param dataset:
        :type dataset: pandas.DataFrame
        :return:
        """

        for column in dataset.columns:
            if str(dataset[column].dtype) == 'category':
                dataset[column] = dataset[column].cat.codes

        return dataset

    # TODO test without it
    # def nodes_at_depth(self, depth):
    #     """
    #     Selects all nodes which are in the given level.
    #
    #     :type depth: int
    #     :param depth: The level to pick
    #     :rtype: list of dict
    #     :return: A list of the nodes at the given level.
    #     """
    #     depths = {k: self.depth_of(k) for k in self._shortest_path.keys()}
    #     at_level = []
    #     for k, d in depths.items():
    #         if d == depth:
    #             at_level.append(self.tree.node[k])
    #     return at_level
    #
    # def parents_of(self, node_id):
    #     """
    #     The parents of the given node.
    #
    #     :type node_id: int
    #     :param node_id: The id of the node, starting from zero (root).
    #     :rtype: list of int
    #     :return: A list of parents of this node, excluding the node itself.
    #     """
    #     parents = copy.deepcopy(self._shortest_path[node_id])
    #     parents.remove(node_id)
    #     return parents
    #
    # def height_and_label_to(self, node_id):
    #     """
    #     Returns a dictionary where the keys are the depth of each one
    #     of the parents, and the values the label of the parents.
    #
    #     :param node_id: ID of the node in the decision tree.
    #     :return:
    #     """
    #     parents = self.parents_of(node_id)
    #     parent_labels = {
    #         self.tree.node[p]['level']: (
    #             self.tree.node[p]['label'] if
    #             self.tree.node[p]['label'] not in DecisionTree.dataset_info.class_labels else
    #             DecisionTree.dataset_info.target_attr
    #         ) for p in parents
    #         }
    #     return parent_labels
    #
    # def depth_of(self, node_id):
    #     """
    #     The depth which a node lies in the tree.
    #
    #     :type node_id: int
    #     :param node_id: The id of the node, starting from zero (root).
    #     :rtype: int
    #     :return: Depth of the node, starting with zero (root).
    #     """
    #
    #     return len(self._shortest_path[node_id]) - 1

    def update(self):
        # TODO info needed to make predictions:
        # preds = make_predictions(
        #     shape,  # shape of sample data
        #     data,  # dataset as a plain list
        #     tree,  # tree in dictionary format
        #     list(range(shape[0])),  # shape of prediction array
        #     self.dataset_info.attribute_index  # dictionary where keys are attributes and values their indices
        # )

        arg_threshold = self.train_index + self.val_index

        self.__set_node__(
            node_id=0,
            subset_index=arg_threshold,
            parent_labels=[],
            coordinates=[],
        )

        raise NotImplementedError('not implemented yet!')

        predictions = np.array(self.mdevice.predict(self.mdevice.dataset, self))

        self.train_acc_score = accuracy_score(DecisionTree.y_train_true, predictions[self.arg_sets['train']])
        self.val_acc_score = accuracy_score(DecisionTree.y_val_true, predictions[self.arg_sets['val']])

        self.fitness = self.train_acc_score

        self.height = max(map(len, self._shortest_path.values()))
        self.n_nodes = len(self.tree.node)

    def predict(self, samples):
        return self.mdevice.predict(samples, self, inner=False)

    def to_matrix(self):
        """
        Converts the inner decision tree from this class to a matrix with n_nodes
        rows and [Left, Right, Terminal, Attribute, Threshold] attributes.
        """
        tree = self.tree

        matrix = pd.DataFrame(
            index=tree.node.keys(),
            columns=['left', 'right', 'terminal', 'attribute', 'threshold']
        )

        conv_dict = {k: i for i, k in enumerate(matrix.index)}

        for node_id, node in tree.node.iteritems():
            label_index = self.dataset_info.class_label_index[node['label']] if \
                              node['terminal'] else self.dataset_info.attribute_index[node['label']]

            matrix.loc[node_id] = [
                conv_dict[self.get_left_child_id(node['node_id'])] if self.get_left_child_id(node_id) in conv_dict else None,
                conv_dict[self.get_right_child_id(node['node_id'])] if self.get_right_child_id(node_id) in conv_dict else None,
                node['terminal'],
                label_index,
                node['threshold']
            ]

        matrix.index = [conv_dict[x] for x in matrix.index]
        matrix = matrix.astype(np.float32)

        return matrix

    def __same_branches__(self, children_left, children_right):
        res = (self.terminal[children_left] and self.terminal[children_right]) and \
               (self.nodes[children_left] == self.nodes[children_right])

        return res

    def __set_node__(self, node_id, subset_index, parent_labels, coordinates):

        '''
        if the current node has only one class,
        or is at a level deeper than maximum depth,
        or the class was sampled
        '''

        label = self.nodes[node_id]

        if any((
            self.get_depth(node_id) >= self.max_depth - 1,
            label == self.class_attr_name,
            len(self.full_df.loc[subset_index, self.class_attr_name].unique()) == 1
        )):
            subset_left, subset_right = self.__set_terminal__(
                node_label=None,
                node_id=node_id,
                subset_index=subset_index,
                parent_labels=parent_labels,
                coordinates=coordinates
            )
        else:
            subset_left, subset_right = self.__set_inner_node__(
                node_label=label,
                node_id=node_id,
                subset_index=subset_index,
                parent_labels=parent_labels,
                coordinates=coordinates,
            )

            if not self.terminal[node_id]:  # continues the process
                children_id = (self.get_left_child_id(node_id), self.get_right_child_id(node_id))
                for child_id, child_subset in zip(children_id, [subset_left, subset_right]):
                    self.__set_node__(
                        node_id=child_id,
                        subset_index=child_subset,
                        parent_labels=parent_labels + [label],
                        coordinates=coordinates
                    )

                # if both branches are terminal, and they share the same class label:
                if self.__same_branches__(children_id[0], children_id[1]):
                    _ = self.__set_terminal__(
                        node_label=label,
                        node_id=node_id,
                        subset_index=subset_index,
                        parent_labels=parent_labels,
                        coordinates=coordinates
                    )

    def __set_inner_node__(self, node_label, node_id, subset_index, parent_labels, coordinates):
        attr_type = self.column_types[node_label]

        subset_left, subset_right = self.handler_dict[attr_type](
            self,
            node_label=node_label,
            node_id=node_id,
            subset_index=subset_index,
            parent_labels=parent_labels,
            coordinates=coordinates
        )

        if self.terminal[node_id]:
            subset_left, subset_right = self.__set_terminal__(
                node_label=None,
                node_id=node_id,
                subset_index=subset_index,
                parent_labels=parent_labels,
                coordinates=coordinates
            )
        elif subset_left.sum() == 0 or subset_right.sum() == 0:  # it is not a terminal, but has no instances to split
            subset_left, subset_right = self.__set_terminal__(
                node_label=None,
                node_id=node_id,
                subset_index=subset_index,
                parent_labels=parent_labels,
                coordinates=coordinates
            )

        return subset_left, subset_right

    def __store_threshold__(self, node_label, parent_labels, coordinates, threshold):
        key = '[' + ','.join(parent_labels + [node_label]) + '][' + ','.join([str(c) for c in coordinates]) + ']'
        self.__class__.thresholds[key] = threshold

    def __retrieve_threshold__(self, node_label, parent_labels, coordinates):
        key = '[' + ','.join(parent_labels + [node_label]) + '][' + ','.join([str(c) for c in coordinates]) + ']'
        return self.__class__.thresholds[key]

    def __set_numerical__(self, node_label, node_id, subset_index, parent_labels, coordinates):
        # TODO not using memory for retrieving already-set thresholds!
        # try:
        #     best_threshold = self.__retrieve_threshold__(node_label, parent_labels, coordinates)
        #     meta, subsets = self.__subsets_and_meta__(
        #         node_label=node_label,
        #         node_id=node_id,
        #         node_level=node_level,
        #         subset_index=subset_index,
        #         threshold=best_threshold,
        #     )
        # except KeyError as ke:
        unique_vals = sorted(self.full_df.loc[subset_index, node_label].unique())

        if len(unique_vals) > 1:
            candidates = np.array(
                [(a + b) / 2. for a, b in zip(unique_vals[::2], unique_vals[1::2])], dtype=np.float32
            )
            gains = gain_ratio(self.full_df.values, subset_index, self.attr_index[node_label], candidates, len(self.class_labels))

            argmax = np.argmax(gains)

            best_gain = gains[argmax]

            if best_gain <= 0:
                subset_left, subset_right = self.__set_terminal__(
                    node_label=node_label,
                    node_id=node_id,
                    subset_index=subset_index,
                    parent_labels=parent_labels,
                    coordinates=coordinates
                )
            else:
                best_threshold = candidates[argmax]
                # self.__store_threshold__(node_label, parent_labels, coordinates, best_threshold)  # TODO deactivated

                self.terminal[node_id] = False
                self.nodes[node_id] = node_label
                self.threshold[node_id] = best_threshold

                less_or_equal = (self.full_df[node_label] <= best_threshold).values.ravel()
                subset_left = less_or_equal & subset_index
                subset_right = np.invert(less_or_equal) & subset_index

        else:
            subset_left, subset_right = self.__set_terminal__(
                node_label=node_label,
                node_id=node_id,
                subset_index=subset_index,
                parent_labels=parent_labels,
                coordinates=coordinates,
            )
        # except Exception as e:
        #     raise e

        return subset_left, subset_right

    def __set_terminal__(self, node_label, node_id, subset_index, parent_labels, coordinates):
        # node_label in this case is probably the DecisionTree.target_attr; so it
        # is not significant for the **real** label of the terminal node.

        counter = Counter(
            map(lambda x: self.class_labels_index[x], self.full_df.loc[subset_index, self.class_attr_name])
        )
        label, count_frequent = counter.most_common()[0]

        self.nodes[node_id] = label
        self.threshold[node_id] = np.nan
        self.terminal[node_id] = True

        return None, None

    def __set_categorical__(self, node_label, node_id, subset_index, parent_labels, coordinates):
        raise TypeError('Unsupported data type for column %s!' % node_label)

    @staticmethod
    def __set_error__(self, node_label, node_id, subset_index, parent_labels, coordinates):
        raise TypeError('Unsupported data type for column %s!' % node_label)

    handler_dict = {
        'numerical': __set_numerical__,
        'categorical': __set_categorical__
    }

    def to_dict(self):
        edges = nx.to_dict_of_dicts(self.tree)
        nodes = self.tree.node
        j = dict(edges=edges, nodes=nodes)
        return j

    def from_json(self, json_string):
        j = json.loads(json_string)
        raise NotImplementedError('not implemented yet!')

    def to_json(self):
        j = self.to_dict()

        for k in j['nodes'].keys():
            j['nodes'][k]['threshold'] = str(j['nodes'][k]['threshold'])

        _str = json.dumps(j, ensure_ascii=False, indent=2)
        return _str