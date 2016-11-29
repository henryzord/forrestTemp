# coding=utf-8
from collections import Counter

import numpy as np
import pandas as pd

from treelib.variable import Variable
from node import *

__author__ = 'Henry Cagnini'


class GraphicalModel(object):
    """
        A graphical model is a tree itself.
    """
    
    attributes = None  # tensor is a dependency graph
    
    def __init__(
            self, pred_attr, target_attr, class_labels, max_depth=3, distribution='multivariate'
    ):

        self.class_labels = class_labels
        self.pred_attr = pred_attr
        self.target_attr = target_attr
        self.distribution = distribution
        self.max_depth = max_depth

        self.attributes = self.__init_attributes__(max_depth, distribution)

    @classmethod
    def clean(cls):
        cls.pred_attr = None
        cls.target_attr = None
        cls.class_labels = None

    def __init_attributes__(self, max_depth, distribution='univariate'):
        def get_parents(_id, _distribution):
            if _distribution == 'multivariate':
                raise NotImplementedError('not implemented yet!')
                # parents = range(_id) if _id > 0 else []
            elif _distribution == 'bivariate':
                raise NotImplementedError('not implemented yet!')
                # parents = [_id - 1] if _id > 0 else []
            elif _distribution == 'univariate':
                parents = []
            else:
                raise ValueError('Distribution must be either \'multivariate\', \'bivariate\' or \'univariate\'!')
            return parents

        sample_values = self.pred_attr + [self.target_attr]

        n_variables = get_total_nodes(max_depth)

        attributes = map(
            lambda i: Variable(
                name=i,
                values=sample_values,
                parents=get_parents(i, distribution),
                max_depth=max_depth,
                target_attr=self.target_attr  # kwargs
            ),
            xrange(n_variables)
        )
        
        return attributes
    
    def update(self, fittest):
        """
        Update attributes' probabilities.

        :type fittest: pandas.Series
        :param fittest:
        :return:
        """

        def get_label(_fit, _node_id):
            if _node_id not in _fit.tree.node:
                return None

            label = _fit.tree.node[_node_id]['label'] \
                if _fit.tree.node[_node_id]['label'] not in self.class_labels \
                else self.target_attr
            return label

        if self.distribution == 'univariate':
            for i, variable in enumerate(self.attributes):
                weights = self.attributes[i].weights

                labels = [get_label(fit, variable.name) for fit in fittest]

                weights['probability'] = 0.

                count = Counter(labels)
                for k, v in count.iteritems():
                    weights.loc[weights[variable.name] == k, 'probability'] = v

                weights['probability'] /= float(weights['probability'].sum())
                rest = abs(weights['probability'].sum() - 1.)
                weights.loc[np.random.choice(weights.index), 'probability'] += rest

                self.attributes[i].weights = weights

        elif self.distribution == 'multivariate':
            raise NotImplementedError('not implemented yet!')

            for height in xrange(self.max_height):  # for each variable in the GM
                c_weights = self.variables[height].weights.copy()  # type: pd.DataFrame
                c_weights['probability'] = 0.

                for ind in fittest:  # for each individual in the fittest population
                    nodes_at_depth = ind.nodes_at_depth(height)
                    for node in nodes_at_depth:
                        parent_labels = ind.height_and_label_to(node['node_id'])

                        node_label = (node['label'] if not node['terminal'] else self.target_attr)
                        ind_weights = c_weights.loc[c_weights[node['level']] == node_label].index

                        if len(parent_labels) > 0:
                            str_ = '&'.join(['(c_weights[%d] == \'%s\')' % (p, l) for (p, l) in parent_labels.iteritems()])
                            p_ind_weights = c_weights[eval(str_)].index
                            ind_weights = set(p_ind_weights) & set(ind_weights)

                        c_weights.loc[ind_weights, 'probability'] += 1

                c_weights['probability'] /= float(c_weights['probability'].sum())
                rest = abs(c_weights['probability'].sum() - 1.)
                c_weights.loc[np.random.choice(c_weights.shape[0]), 'probability'] += rest
                self.variables[height].weights = c_weights
                # print c_weights
        elif self.distribution == 'bivariate':
            raise NotImplementedError('not implemented yet!')

    def sample(self, node_id, level, parent_labels=None, enforce_nonterminal=False):
        value = self.attributes[node_id].get_value(parent_labels=parent_labels)
        if enforce_nonterminal:
            while value == self.target_attr:
                value = self.attributes[node_id].get_value(parent_labels=parent_labels)

        return value
