# coding=utf-8
from treelib.graphical_models import *

__author__ = 'Henry Cagnini'


class Ardennes(AbstractTree):
    gm = None
    
    def __init__(self, n_individuals=100, n_iterations=100, uncertainty=0.01, decile=0.9, **kwargs):
        """
        Default EDA class, with common code to all EDAs -- regardless
        of the complexity of inner GMs or updating techniques.

        :type n_individuals: int
        :param n_individuals: Number of maximum individuals for a any population, throughout the evolutionary process.
        :param n_iterations: First (and most likely to be reached) stopping criterion. Maximum number of generations
            that this EDA is allowed to produce.
        :param uncertainty: Second stopping criterion. If this EDA's GM presents an uncertainty lesser than this
            parameter, then this EDA will likely stop before reaching the maximum number of iterations.
        :param decile: A parameter for determining how much of the population must be used for updatign the GM, and also
            how much of it must be resampled for the next generation. For example, if decile=0.9, then 10% of the
            population will be used for GM updating and 90% will be resampled.
        """
        super(Ardennes, self).__init__(**kwargs)
        
        self.n_individuals = n_individuals
        self.n_iterations = n_iterations
        self.uncertainty = uncertainty
        self.decile = decile

        self.trained = False
        self.best_individual = None
        self.last_population = None

    def fit(self, sets=None, X_train=None, y_train=None, X_val=None, y_val=None, verbose=True, **kwargs):
        if sets is None or 'train' not in sets:
            if all(map(lambda x: x is None, [X_train, y_train])):
                raise KeyError('You need to pass at least a train set to this method!')
            else:
                sets = dict()
                
                sets['train'] = pd.DataFrame(
                    np.hstack((X_train, y_train[:, np.newaxis]))
                )
                
                if all(map(lambda x: x is None, [X_val, y_val])):
                    sets['val'] = sets['train']
                else:
                    sets['val'] = pd.DataFrame(
                        np.hstack((X_val, y_val[:, np.newaxis]))
                    )
        else:
            if 'val' not in sets:
                sets['val'] = sets['train']

        output_file = kwargs['output_file'] if 'output_file' in kwargs else None

        class_values = {
            'pred_attr': list(sets['train'].columns[:-1]),
            'target_attr': sets['train'].columns[-1],
            'class_labels': list(sets['train'][sets['train'].columns[-1]].unique())
        }

        self.pred_attr = class_values['pred_attr']
        self.target_attr = class_values['target_attr']
        self.class_labels = class_values['class_labels']

        if 'initial_tree_size' in kwargs:
            self.__check_tree_size__(kwargs['initial_tree_size'])
            initial_tree_size = kwargs['initial_tree_size']
        else:
            initial_tree_size = 3

        # threshold where individuals will be picked for PMF updating/replacing
        integer_threshold = int(self.decile * self.n_individuals)

        df_replace = pd.DataFrame(np.empty((self.n_individuals - integer_threshold, initial_tree_size), dtype=np.object))

        gm = GraphicalModel(
            initial_tree_size=initial_tree_size,
            distribution=kwargs['distribution'] if 'distribution' in kwargs else 'multivariate',
            class_probability=kwargs['class_probability'] if 'class_probability' in kwargs else None,
            **class_values
        )
        
        population = self.sample_individuals(
            df=df_replace.append(  # TODO error here!
                pd.DataFrame(np.empty((integer_threshold, initial_tree_size), dtype=np.object))
            ),
            graphical_model=gm,
            sets=sets
        )
        
        fitness = np.array(map(lambda x: x.fitness, population))

        iteration = 0
        while iteration < self.n_iterations:  # evolutionary process
            self.__report__(
                iteration=iteration,
                fitness=fitness,
                verbose=verbose,
                output_file=output_file
            )

            borderline = np.partition(fitness, integer_threshold)[integer_threshold]
            
            # picks fittest population
            fittest_pop = self.__pick_fittest_population__(population, borderline)
            gm.update(fittest_pop)
            
            n_replace = np.count_nonzero(fitness < borderline)
            replaced = self.sample_individuals(n_replace, gm, sets)
            population = fittest_pop + replaced
            
            if self.__early_stop__(gm, self.uncertainty):
                break
            
            fitness = np.array(map(lambda x: x.fitness, population))
            
            iteration += 1

        self.best_individual = np.argmax(fitness)
        self.last_population = population
        self.trained = True
        GraphicalModel.reset_globals()

    def predict_proba(self, samples, ensemble=False):
        df = self.__to_dataframe__(samples)

        if not ensemble:
            # using predict_proba with a single tree has the same effect as simply using predict
            predictor = self.last_population[self.best_individual]
            all_preds = predictor.predict(df)
        else:
            predictor = self.last_population

            labels = {label: i for i, label in enumerate(self.class_labels)}

            def sample_prob(sample):
                preds = np.empty(len(self.class_labels), dtype=np.float32)

                sample_predictions = map(lambda x: x.predict(sample), predictor)
                count = Counter(sample_predictions)
                count_probs = {k: v / float(len(predictor)) for k, v in count.iteritems()}
                for k, v in count_probs.items():
                    preds[labels[k]] = v

                return preds

            all_preds = df.apply(sample_prob, axis=1).as_matrix()

        return all_preds

    def predict(self, samples, ensemble=False):
        df = self.__to_dataframe__(samples)

        if not ensemble:
            predictor = self.last_population[self.best_individual]
            all_preds = predictor.predict(df)
        else:
            predictor = self.last_population

            def sample_pred(sample):
                sample_predictions = map(lambda x: x.predict(sample), predictor)
                most_common = Counter(sample_predictions).most_common()[0][0]
                return most_common

            all_preds = df.apply(sample_pred, axis=1).as_matrix()

        return all_preds

    def validate(self, test_set=None, X_test=None, y_test=None, ensemble=False):
        """
        Assess the accuracy of this instance against the provided set.

        :type test_set: pandas.DataFrame
        :param test_set: a matrix with the class attribute in the last position (i.e, column).
        :rtype: float
        :return: The accuracy of this model when testing with test_set.
        """

        if test_set is None:
            test_set = pd.DataFrame(
                np.hstack((X_test, y_test[:, np.newaxis]))
            )

        predictions = self.predict(test_set, ensemble=ensemble)
        acc = (test_set[test_set.columns[-1]] == predictions).sum() / float(test_set.shape[0])
        return acc

    def plot(self):
        raise NotImplementedError('not implemented yet!')

    @staticmethod
    def sample_individuals(df, graphical_model, sets):
        df.reset_index(drop=True, inplace=True)
        df = graphical_model.sample(df)

        raise NotImplementedError('implement with apply!')

        sample = map(
            lambda i: Individual(id=i, sess=df.iloc[i], sets=sets),
            xrange(n_sample)
        )
        return sample

    @staticmethod
    def __to_dataframe__(samples):
        if isinstance(samples, np.ndarray) or isinstance(samples, list):
            df = pd.DataFrame(samples)
        elif isinstance(samples, pd.DataFrame):
            df = samples
        else:
            raise TypeError('Invalid type for samples! Must be either a list-like or a pandas.DataFrame!')

        return df

    @staticmethod
    def __pick_fittest_population__(population, borderline):
        fittest_pop = []
        for ind in population:
            if ind.fitness >= borderline:
                fittest_pop += [ind]

        return fittest_pop

    @staticmethod
    def __report__(**kwargs):
        iteration = kwargs['iteration']  # type: int

        fitness = kwargs['fitness']  # type: np.ndarray

        if kwargs['verbose']:
            mean = np.mean(fitness)  # type: float
            median = np.median(fitness)  # type: float
            max_fitness = np.max(fitness)  # type: float

            print 'iter: %03.d\tmean: %+0.6f\tmedian: %+0.6f\tmax: %+0.6f' % (iteration, mean, median, max_fitness)

        if kwargs['output_file']:
            output_file = kwargs['output_file']  # type: str
            with open(output_file, 'a') as f:
                np.savetxt(f, fitness[:, np.newaxis].T, delimiter=',')
    
    @staticmethod
    def __early_stop__(gm, uncertainty=0.01):
        """

        :type gm: treelib.graphical_models.GraphicalModel
        :param gm: The Probabilistic Graphical Model (GM) for the current generation.
        :type uncertainty: float
        :param uncertainty: Maximum allowed uncertainty for each probability, for each node.
        :return:
        """
        
        should_stop = True
        for tensor in gm.tensors:
            weights = tensor.weights
            upper = abs(1. - weights['probability'].max())
            lower = weights['probability'].min()
            
            if upper > uncertainty or lower > uncertainty:
                should_stop = False
                break

        return should_stop

    @staticmethod
    def __check_tree_size__(initial_tree_size):
        if (initial_tree_size - 1) % 2 != 0:
            raise ValueError('Invalid number of nodes! (initial_tree_size - 1) % 2 must be an integer!')
