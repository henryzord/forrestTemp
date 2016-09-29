from collections import Counter

import numpy as np
import xarray

from treelib.classes import SetterClass, Session, AbstractTree
from treelib.individual import Individual
import itertools as it
import operator as op
import pandas as pd

__author__ = 'Henry Cagnini'


class Tensor(SetterClass):
    global_gms = dict()
    
    def __init__(self, name, values, parents=None, probability='uniform', gm_id=0, **kwargs):
        super(Tensor, self).__init__(**kwargs)
        
        if gm_id not in self.__class__.global_gms:
            self.__class__.global_gms[gm_id] = dict()
        
        if name in self.__class__.global_gms[gm_id]:
            raise KeyError('Variable is already defined for this scope!')  # name is also an axis
        
        self.gm_id = gm_id  # type: float
        self.name = name  # type: int
        self.parents = parents if parents is not None else []
        self.values = values  # type: list of str
        
        # self.reverse_values = {k: i for i, k in enumerate(values)}  # type: dict of str
        
        self.weights = self.__init_probabilities__(values, probability)  # type: np.ndarray
        
        self.__class__.global_gms[gm_id][name] = self
    
    @property
    def n_parents(self):
        return len(self.parents)
    
    @property
    def n_values(self):
        return len(self.values)
    
    def __init_probabilities__(self, values, probability='uniform'):
        if probability == 'uniform':
            vec_vals = [self.values] + [self.global_gms[self.gm_id][p].values for p in self.parents]
            
            combs = list(it.product(*vec_vals))
            columns = [self.name] + [self.global_gms[self.gm_id][p].name for p in self.parents]
            
            df = pd.DataFrame(
                data=combs,
                columns=columns
            )
            df['probability'] = 1. / df.shape[0]  # TODO maybe is wrong! must be conditional to the parent!
            return df
        elif isinstance(probability, list):
            if len(probability) != len(values):
                raise IndexError('number of weights must be the same as the number of values!')
            else:
                # TODO guarantee that weights have the same order than values!
                raise NotImplementedError('not implemented yet!')
        else:
            raise TypeError('probability must be either a string or a list!')
    
    def sample(self, session):
        if self.name in session:
            raise KeyError('value already sampled in this session!')
        if len(self.parents) == 0:  # TODO now must calculate conditional probabilities!
            p = self.weights['probability']
            a = self.weights[self.name]
        else:
            grouped = self.weights.copy()  # type: pd.DataFrame
            for p in self.parents:
                grouped = grouped.loc[grouped[p] == session[p]]
            
            _sum = grouped['probability'].sum()
            
            grouped['probability'] = grouped['probability'].apply(lambda x: x / _sum)

            a = grouped[self.name]
            p = grouped['probability']
        
        value = np.random.choice(a=a, p=p)  # weights has the same order than values
        session[self.name] = value
        return value


class GraphicalModel(AbstractTree):
    """
        A graphical model is a tree itself.
    """
    
    tensors = None  # tensor is a dependency graph
    
    def __init__(self, pattern=None, gm_id=0, **kwargs):
        super(GraphicalModel, self).__init__(**kwargs)
        
        self.gm_id = gm_id
        
        if pattern is None:
            self.tensors = self.__init_tensor__()
        else:
            raise NotImplementedError('not implemented yet!')
    
    def __init_tensor__(self):
        """
        Initializes a simple 3 nodes tree.
        
        :rtype: list
        :return: A list of 3 tensors.
        """
        # TODO enhance to perform any kind of initialization!
        
        tensors = [
            Tensor(0, self.pred_attr, gm_id=self.gm_id),
            Tensor(1, [self.target_attr], [0], gm_id=self.gm_id),
            Tensor(2, [self.target_attr], [0], gm_id=self.gm_id)
        ]
        
        return tensors
    
    def update(self, fittest):
        """
        
        :type fittest: list of Individual
        :param fittest:
        :return:
        """
        
        n_fittest = float(len(fittest))
        
        for i, tensor in enumerate(self.tensors):
            parents = tensor.parents
            order = [tensor.name] + parents
        
            all_vec = []
            for fit in fittest:
                vec = map(
                    lambda x: fit.tree.node[x]['label'],
                    order
                )
                all_vec += [tuple(vec)]

            count = Counter(all_vec)
            weights = tensor.weights  # type: pd.DataFrame
            weights['probability'] = 0.
            
            for comb, n_occur in count.iteritems():
                click = it.izip(order, comb)
                _slice = weights  # type: pd.DataFrame
                for var_name, value in click:
                    _slice = weights.loc[weights[var_name] == value]
                
                _slice['probability'] = n_occur
                weights['probability'][_slice.index] = _slice['probability']  # TODO not assigning correctly!

            print weights
            weights['probability'] = weights['probability'].apply(lambda x: x / n_fittest)
            print weights
            
            tensor.weights = weights
            self.tensors[i].weights = weights
    
    def sample(self):
        sess = Session()
        
        for tensor in self.tensors:
            tensor.sample(sess)
        
        return sess
