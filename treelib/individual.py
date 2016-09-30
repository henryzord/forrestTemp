# coding=utf-8

import itertools as it
from collections import Counter

import networkx as nx
import numpy as np
import pandas as pd

from treelib.classes import AbstractTree
from treelib.node import Node

from matplotlib import pyplot as plt

__author__ = 'Henry Cagnini'


class Individual(AbstractTree):
    _terminal_node_color = '#98FB98'
    _inner_node_color = '#0099ff'
    _root_node_color = '#FFFFFF'
    column_types = None  # type: dict
    sets = None  # type: dict
    tree = None  # type: nx.DiGraph
    val_acc = None  # type: float
    id = None
    
    def __init__(self, graphical_model, sets, **kwargs):
        """
        
        :type graphical_model: treelib.graphical_models.GraphicalModel
        :param graphical_model:
        :type sets: dict
        :param sets:
        :type kwargs: dict
        :param kwargs:
        """
        super(Individual, self).__init__(**kwargs)

        if 'id' in kwargs:
            self.id = kwargs['id']

        if Individual.column_types is None:
            Individual.column_types = {
                x: self.type_handler_dict[str(sets['train'][x].dtype)] for x in sets['train'].columns
            }  # type: dict
            Individual.column_types['class'] = 'class'
        self.column_types = Individual.column_types
        
        self.sets = sets
        self.sample(graphical_model, sets)

    def __str__(self):
        return 'fitness: %0.2f' % self.val_acc

    def plot(self):
        """
        Plots this individual.
        """
    
        fig = plt.figure()
    
        tree = self.tree  # type: nx.DiGraph
        pos = nx.spectral_layout(tree)
    
        node_list = tree.nodes(data=True)
        edge_list = tree.edges(data=True)
    
        node_labels = {x[0]: x[1]['label'] for x in node_list}
        node_colors = [x[1]['color'] for x in node_list]
        edge_labels = {(x1, x2): d['threshold'] for x1, x2, d in edge_list}
    
        nx.draw_networkx_nodes(tree, pos, node_size=1000, node_color=node_colors)  # nodes
        nx.draw_networkx_edges(tree, pos, edgelist=edge_list, style='dashed')  # edges
        nx.draw_networkx_labels(tree, pos, node_labels, font_size=16)  # node labels
        nx.draw_networkx_edge_labels(tree, pos, edge_labels=edge_labels, font_size=16)
    
        plt.text(
            0.8,
            0.9,
            'Fitness: %0.4f' % self.val_acc,
            fontsize=15,
            horizontalalignment='center',
            verticalalignment='center',
            transform=fig.transFigure
        )
    
        if self.id is not None:
            plt.text(
                0.1,
                0.1,
                'ID: %03.d' % self.id,
                fontsize=15,
                horizontalalignment='center',
                verticalalignment='center',
                transform=fig.transFigure
            )
    
        plt.axis('off')

    @property
    def fitness(self):
        """
        :rtype: float
        :return: Fitness of this individual.
        """
        return self.val_acc

    # ############################ #
    # sampling and related methods #
    # ############################ #

    def sample(self, graphical_model, sets):
        sess = graphical_model.sample()

        self.tree = self.__set_thresholds__(sess, sets['train'])  # type: nx.DiGraph
        self.val_acc = self.__validate__(self.sets['val'])

    def __set_thresholds__(self, sess, train_set):
        """
        
        :type sess: dict of float
        :param sess:
        :type train_set: pandas.DataFrame
        :param train_set:
        :rtype: networkx.DiGraph
        :return:
        """

        tree = nx.DiGraph()
    
        subset = train_set
    
        tree = self.__set_node_threshold__(
            sess=sess,
            tree=tree,
            subset=subset,
            variable_name=0,
            parent_label=0
        )
        return tree

    def __set_node_threshold__(self, sess, tree, subset, variable_name, parent_label):
        """
        
        :param sess:
        :type tree: networkx.DiGraph
        :param tree:
        :param subset:
        :param variable_name:
        :return:
        """
        
        if subset.shape[0] <= 0 or sess[variable_name] == Individual.target_attr:
            meta, subset_left, subset_right = self.__set_terminal__(
                variable_name=variable_name,
                node_label=sess[variable_name],
                parent_label=parent_label,
                subset=subset
            )
        else:
            meta, subset_left, subset_right = self.__set_inner_node__(
                variable_name=variable_name,
                parent_label=parent_label,
                subset=subset,
                sess=sess
            )

        id_left, id_right = (Node.get_left_child(variable_name), Node.get_right_child(variable_name))
        if id_left in sess and id_right in sess:
            for (id_child, child_subset) in it.izip([id_left, id_right], [subset_left, subset_right]):
                tree = self.__set_node_threshold__(
                    sess=sess,
                    tree=tree,
                    subset=child_subset,
                    variable_name=id_child,
                    parent_label=meta['label']
                )

            if meta['threshold'] is not None:
                attr_dict_left = {'threshold': '< %0.2f' % meta['threshold']}
                attr_dict_right = {'threshold': '>= %0.2f' % meta['threshold']}
            else:
                attr_dict_left = {'threshold': None}
                attr_dict_right = {'threshold': None}
            
            tree.add_edge(variable_name, id_left, attr_dict=attr_dict_left)
            tree.add_edge(variable_name, id_right, attr_dict=attr_dict_right)

        tree.add_node(variable_name, attr_dict=meta)
        return tree
        
    @staticmethod
    def entropy(subset, target_attr):
        # the smaller, the better
        size = float(subset.shape[0])

        counter = Counter(subset[target_attr])

        _entropy = 0.
        for c, q in counter.iteritems():
            _entropy += (q / size) * np.log2(q / size)

        return -1. * _entropy

    def __validate_object__(self, obj):
        arg_node = 0

        tree = self.tree  # type: nx.DiGraph

        node = self.tree.node[arg_node]
        successors = tree.successors(arg_node)
        
        while not node['terminal']:
            go_left = obj[node['label']] < node['threshold']
            arg_node = (int(go_left) * min(successors)) + (int(not go_left) * max(successors))
            successors = tree.successors(arg_node)
            node = tree.node[arg_node]

        return obj[-1] == node['label']

    def __validate__(self, test_set):
        """
        Assess the accuracy of this Individual against the provided set.
        
        :type test_set: pandas.DataFrame
        :param test_set: a matrix with the class attribute in the last position (i.e, column).
        :return: The accuracy of this model when testing with test_set.
        """
        
        hit_count = test_set.apply(self.__validate_object__, axis=1).sum()
        acc = hit_count / float(test_set.shape[0])
        return acc

    def __set_inner_node__(self, variable_name, parent_label, subset, sess, **kwargs):
        attr_type = Individual.column_types[sess[variable_name]]
        out = self.attr_handler_dict[attr_type](
            self,
            node_label=sess[variable_name],
            parent_label=parent_label,
            subset=subset,
            variable_name=variable_name,
            **kwargs
        )
        return out

    def __set_numerical__(self, node_label, parent_label, subset, **kwargs):
        # pd.options.mode.chained_assignment = None
        
        def slide_filter(x):
            """
            Verifies if two neighboring objects have the same class.
            
            :type x: pandas.core.series.Series
            :param x: An object with a predictive attribute and the class attribute.
            :rtype: bool
            :return: True if the neighbor of x have the same class; False otherwise.
            """
            
            first = ((x.name - 1) * (x.name > 0)) + (x.name * (x.name <= 0))
            second = x.name
            column = Individual.target_attr
            
            return ss[column].iloc[first] == ss[column].iloc[second]

        def get_entropy(threshold):
            """
            Gets entropy for a given threshold.
            
            :type threshold: float
            :param threshold: Threshold value.
            :rtype: float
            :return: the entropy.
            """
            
            subset_left = subset.loc[subset[node_label] < threshold]
            subset_right = subset.loc[subset[node_label] >= threshold]
            
            entropy = \
                Individual.entropy(subset_left, Individual.target_attr) + \
                Individual.entropy(subset_right, Individual.target_attr)

            return entropy

        ss = subset[[node_label, Individual.target_attr]]  # type: pd.DataFrame
        ss = ss.sort_values(by=node_label).reset_index()

        ss['change'] = ss.apply(slide_filter, axis=1)
        unique_vals = ss.loc[ss['change'] == False]
        
        if unique_vals.empty:
            meta, best_subset_left, best_subset_right = self.__set_terminal__(
                node_label=Individual.target_attr, parent_label=parent_label, subset=subset, **kwargs
            )
        else:
            unique_vals['entropy'] = unique_vals[node_label].apply(get_entropy)
            best_entropy = unique_vals['entropy'].min()
            
            best_threshold = (unique_vals[unique_vals['entropy'] == best_entropy])[node_label].values[0]
            
            best_subset_left = subset.loc[subset[node_label] < best_threshold]
            best_subset_right = subset.loc[subset[node_label] >= best_threshold]

            meta = {
                'label': node_label,
                'threshold': best_threshold,
                'terminal': False,
                'color': Individual._root_node_color if
                    kwargs['variable_name'] == Node.root else Individual._inner_node_color
            }
            # pd.options.mode.chained_assignment = 'warn'

        if 'get_meta' in kwargs and kwargs['get_meta'] == False:
            return best_subset_left, best_subset_right
        else:
            return meta, best_subset_left, best_subset_right
    
    def __set_terminal__(self, node_label, parent_label, subset, **kwargs):
        if not subset.empty:
            count = Counter(subset[node_label])
    
            f_key = None
            f_val = -np.inf
            for key, val in count.iteritems():
                if val > f_val:
                    f_key = key
                    f_val = val
        else:
            f_key = parent_label

        meta = {
            'label': f_key,
            'threshold': None,
            'terminal': True,
            'color': Individual._terminal_node_color
        }
        return meta, pd.DataFrame([]), pd.DataFrame([])

    def __set_categorical__(self, node_label, parent_label, subset, **kwargs):
        raise NotImplemented('not implemented yet!')

    @staticmethod
    def __set_error__(self, node_label, parent_label, subset, **kwargs):
        raise TypeError('Unsupported data type for column %s!' % attr_name)

    attr_handler_dict = {
        'object': __set_categorical__,
        'str': __set_categorical__,
        'int': __set_numerical__,
        'float': __set_numerical__,
        'bool': __set_categorical__,
        'complex': __set_error__,
        'class': __set_terminal__
    }

    type_handler_dict = {
        'bool': 'bool',
        'bool_': 'bool',
        'int': 'int',
        'int_': 'int',
        'intc': 'int',
        'intp': 'int',
        'int8': 'int',
        'int16': 'int',
        'int32': 'int',
        'int64': 'int',
        'uint8': 'int',
        'uint16': 'int',
        'uint32': 'int',
        'uint64': 'int',
        'float': 'float',
        'float_': 'float',
        'float16': 'float',
        'float32': 'float',
        'float64': 'float',
        'complex_': 'complex',
        'complex64': 'complex',
        'complex128': 'complex',
        'str': 'str',
        'object': 'object'
    }
