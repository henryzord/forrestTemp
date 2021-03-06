# coding=utf-8
import copy
import random
import warnings
from datetime import datetime as dt

from device import AvailableDevice
from graphical_model import *
from individual import Individual
from treelib.individual import DecisionTree
from utils import MetaDataset, DatabaseHandler

__author__ = 'Henry Cagnini'


class Ardennes(object):
    val_str = 'val_df'
    train_str = 'train_df'
    test_str = 'test_df'

    def __init__(self, n_individuals, n_iterations, max_height=3):

        self.n_individuals = n_individuals

        self.D = max_height - 1
        self.n_iterations = n_iterations

        self.trained = False
        self.predictor = None

    @staticmethod
    def __initialize_argsets__(full, train, val, test):
        _arg_sets = dict()

        train_index = np.zeros(full.shape[0], dtype=np.bool)
        val_index = np.zeros(full.shape[0], dtype=np.bool)
        test_index = np.zeros(full.shape[0], dtype=np.bool)

        train_index[train.index] = 1
        val_index[val.index] = 1
        test_index[test.index] = 1

        _arg_sets['train'] = train_index
        _arg_sets['val'] = val_index
        _arg_sets['test'] = test_index

        return _arg_sets

    def __setup__(self, train_set, **kwargs):
        """

        :type train_set: pandas.DataFrame
        :param train_set:
        :param kwargs:
        :return:
        """

        if 'random_state' in kwargs and kwargs['random_state'] is not None:
            random_state = kwargs['random_state']
            warnings.warn('WARNING: Using non-randomic sampling with seed=%d' % random_state)
        else:
            random_state = None

        if 'dbhandler' in kwargs:
            dbhandler = kwargs['dbhandler']  # type: utils.DatabaseHandler
        else:
            dbhandler = None

        random.seed(random_state)
        np.random.seed(random_state)

        full = copy.deepcopy(train_set)

        metadatas = [dict(
            relation_name='train', hashkey=DatabaseHandler.get_hash(train_set),
            n_instances=train_set.shape[0], n_attributes=train_set.shape[1],
            n_classes=len(train_set[train_set.columns[-1]].unique())
        )]

        if Ardennes.val_str in kwargs and kwargs[Ardennes.val_str] is not None:
            val_set = kwargs[Ardennes.val_str]
            val_set.index = pd.RangeIndex(full.index[-1] + 1, full.index[-1] + 1 + val_set.shape[0], 1)
            full = full.append(val_set, ignore_index=True)

            metadatas += [dict(
                relation_name='val', hashkey=DatabaseHandler.get_hash(val_set),
                n_instances=val_set.shape[0], n_attributes=val_set.shape[1],
                n_classes=len(val_set[val_set.columns[-1]].unique())
            )]

        else:
            val_set = train_set  # type: pd.DataFrame

        if Ardennes.test_str in kwargs and kwargs[Ardennes.test_str] is not None:
            test_set = kwargs[Ardennes.test_str]
            test_set.index = pd.RangeIndex(full.index[-1] + 1, full.index[-1] + 1 + test_set.shape[0], 1)
            full = full.append(test_set, ignore_index=True)

            metadatas += [dict(
                relation_name='test', hashkey=DatabaseHandler.get_hash(test_set),
                n_instances=test_set.shape[0], n_attributes=test_set.shape[1],
                n_classes=len(test_set[test_set.columns[-1]].unique())
            )]

        else:
            test_set = train_set  # type: pd.DataFrame

        metadatas += [dict(
            relation_name='full', hashkey=DatabaseHandler.get_hash(full),
            n_instances=full.shape[0], n_attributes=full.shape[1],
            n_classes=len(full[full.columns[-1]].unique())
        )]

        if dbhandler is not None:
            dbhandler.write_sets(metadatas)

        arg_sets = self.__initialize_argsets__(full, train_set, val_set, test_set)

        dataset_info = MetaDataset(full)

        mdevice = AvailableDevice(full, dataset_info)

        DecisionTree.set_values(
            arg_sets=arg_sets,
            y_train_true=full.loc[arg_sets['train'], dataset_info.target_attr],
            y_val_true=full.loc[arg_sets['val'], dataset_info.target_attr],
            y_test_true=full.loc[arg_sets['test'], dataset_info.target_attr],
            processor=mdevice,
            dataset_info=dataset_info,
            max_height=self.D,
            dataset=full,
            mdevice=mdevice,
            multi_tests=kwargs['multi_tests']
        )

        gm = GraphicalModel(
            D=self.D,
            dataset_info=dataset_info,
            multi_tests=kwargs['multi_tests']
        )

        return gm

    def fit(self, train_df, decile, verbose=True, **kwargs):
        """
        Fits the algorithm to the provided data.
        """

        assert 1 <= int(self.n_individuals * decile) <= self.n_individuals, \
            ValueError('Decile must comprise at least one individual and at maximum the whole population!')

        gm = self.__setup__(train_set=train_df, **kwargs)

        sample_func = np.vectorize(Individual, excluded=['gm', 'iteration'])

        population = np.empty(shape=self.n_individuals, dtype=Individual)
        to_replace_index = np.arange(self.n_individuals, dtype=np.int32)

        '''
        Main loop
        '''
        iteration = 0

        while iteration < self.n_iterations:
            t1 = dt.now()  # starts measuring time

            fitness, population = self.sample_population(gm, iteration, sample_func, to_replace_index, population)

            to_replace_index, fittest_pop = self.split_population(decile, population)

            # TODO use only when in mtst!
            # warnings.warn('WARNING: testing new ideas!')
            # best_individual = self.get_best_individual(population)
            # DecisionTree.max_height = best_individual.height
            # warnings.warn('WARNING: testing new ideas!')

            gm.update(fittest_pop)

            t2 = dt.now()
            self.__report__(
                iteration=iteration,
                population=population,
                fitness=fitness,
                verbose=verbose,
                elapsed_time=(t2 - t1).total_seconds(),
                gm=gm,
                **kwargs
            )

            if self.__early_stop__(population):
                break

            iteration += 1

        self.predictor = self.get_best_individual(population)
        self.trained = True

    @staticmethod
    def sample_population(gm, iteration, func, to_replace_index, population):
        """

        :type gm: treelib.graphical_model.GraphicalModel
        :param gm: Current graphical model.
        :type iteration: int
        :param iteration: Current iteration.
        :param func: Sample function.
        :type to_replace_index: list
        :param to_replace_index: List of indexes of individuals to be replaced in the following generation.
        :type population: numpy.ndarray
        :param population: Current population.
        :rtype: tuple
        :return: A tuple where the first item is the population fitness and the second the population.
        """

        population.flat[to_replace_index] = func(
            ind_id=[population[i].ind_id for i in to_replace_index] if iteration > 0 else to_replace_index,
            gm=gm,
            iteration=iteration
        )
        population.sort()  # sorts using quicksort, worst individual to best
        population = population[::-1]  # reverses list so the best individual is in the beginning

        fitness = np.array([x.fitness for x in population])

        return fitness, population

    def split_population(self, decile, population):
        integer_decile = int(self.n_individuals * decile)

        # refers to indices in the array, not in the population (i.e. individual.ind_id)
        to_replace_index = range(self.n_individuals)[integer_decile:]
        fittest_pop = population[:integer_decile]

        return to_replace_index, fittest_pop

    @staticmethod
    def get_best_individual(population):
        outer_fitness = [0.5 * (ind.train_acc_score + ind.val_acc_score) for ind in population]
        return population[np.argmax(outer_fitness)]

    @property
    def tree_height(self):
        if self.trained:
            return self.predictor.height

    def __report__(self, **kwargs):
        # required data, albeit this method has only a kwargs dictionary
        iteration = kwargs['iteration']  # type: int
        population = kwargs['population']
        verbose = kwargs['verbose']
        elapsed_time = kwargs['elapsed_time']
        fitness = kwargs['fitness']
        gm = kwargs['gm']

        best_individual = self.get_best_individual(population)

        # optional data
        dbhandler = None if 'dbhandler' not in kwargs else kwargs['dbhandler']  # type: utils.DatabaseHandler

        if verbose:
            mean = np.mean(fitness)  # type: float
            median = np.median(fitness)  # type: float

            print 'iter: %03.d mean: %0.6f median: %0.6f max: %0.6f ET: %02.2fsec  height: %2.d  n_nodes: %2.d  ' % (
                iteration, mean, median, best_individual.fitness, elapsed_time, best_individual.height, best_individual.n_nodes
            ) + ('test acc: %0.6f' % best_individual.test_acc_score if best_individual.test_acc_score is not None else '')

        if dbhandler is not None:
            dbhandler.write_prototype(iteration, gm)
            dbhandler.write_population(iteration, population)

    @staticmethod
    def __early_stop__(population):
        return population.min() == population.max()

    def predict(self, test_set):
        y_test_pred = list(self.predictor.predict(test_set))
        return y_test_pred
