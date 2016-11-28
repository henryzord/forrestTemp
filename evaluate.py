# coding=utf-8

"""
Performs tests in an 'industrial' fashion.
"""

import json
import os
import itertools as it
import pandas as pd
import arff

from main import do_train
import numpy as np

__author__ = 'Henry Cagnini'


def evaluate_j48(datasets_path, folds_path):
    import weka.core.jvm as jvm
    from weka.core.converters import Loader
    from weka.classifiers import Classifier

    jvm.start()

    results = dict()

    try:
        for dataset in os.listdir(folds_path):
            dataset_name = dataset.split('.')[0]

            results[dataset_name] = dict()

            print 'doing for dataset %s' % dataset_name

            fold_file = json.load(open(os.path.join(folds_path, dataset_name + '.json'), 'r'))
            arff_dtst = arff.load(open(os.path.join(datasets_path, dataset_name + '.arff'), 'r'))

            loader = Loader(classname="weka.core.converters.CSVLoader")

            for n_fold, folds_sets in fold_file.iteritems():
                attributes = [x[0] for x in arff_dtst['attributes']]
                np_train_s = pd.DataFrame(arff_dtst['data'], columns=attributes)
                np_test_s = pd.DataFrame(arff_dtst['data'], columns=attributes)

                np_train_s = np_train_s.loc[folds_sets['train'] + folds_sets['val']]
                np_test_s = np_test_s.loc[folds_sets['test']]

                np_train_s.to_csv('.train_temp.csv', index=False)
                np_test_s.to_csv('.test_temp.csv', index=False)

                train_s = loader.load_file('.train_temp.csv')
                test_s = loader.load_file('.test_temp.csv')
                train_s.class_is_last()
                test_s.class_is_last()

                cls = Classifier(classname="weka.classifiers.trees.J48", options=["-C", "0.25", "-M", "2"])
                cls.build_classifier(train_s)

                acc = 0.
                for index, inst in enumerate(test_s):
                    pred = cls.classify_instance(inst)
                    real = inst.get_value(inst.class_index)
                    acc += (pred == real)

                acc /= float(test_s.num_instances)

                results[dataset_name][n_fold] = acc

                print 'dataset %s %d-th fold accuracy: %02.2f' % (dataset_name, int(n_fold), acc)

                os.remove('.train_temp.csv')
                os.remove('.test_temp.csv')

        json.dump(results, open('j48_results.json', 'w'), indent=2)

    finally:
        jvm.stop()

        try:
            os.remove('.train_temp.csv')
        except OSError:
            pass
        try:
            os.remove('.test_temp.csv')
        except OSError:
            pass


def evaluate_several(datasets_path, output_path, validation_mode='cross-validation', n_jobs=2):
    datasets = os.listdir(datasets_path)
    np.random.shuffle(datasets)  # everyday I'm shuffling

    config_file = json.load(open('config.json', 'r'))

    for i, dataset in enumerate(datasets):
        config_file['dataset_path'] = os.path.join(datasets_path, dataset)

        try:
            do_train(
                config_file=config_file,
                output_path=output_path,
                evaluation_mode=validation_mode
            )
        except:
            import warnings
            warnings.warn('exception found when running %s!' % dataset)


if __name__ == '__main__':
    _datasets_path = 'datasets/numerical'
    _folds_path = 'datasets/folds'
    _output_path = 'metadata'
    _validation_mode = 'cross-validation'

    evaluate_several(
        datasets_path=_datasets_path,
        output_path=_output_path,
        validation_mode=_validation_mode,
        n_jobs=2
    )

    # evaluate_j48(_datasets_path, _folds_path)
