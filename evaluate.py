# coding=utf-8

"""
Performs tests in an 'industrial' fashion.
"""
import glob
import os
import csv
import json
import shutil
import warnings
import StringIO
import pandas as pd
import operator as op
import networkx as nx
import itertools as it
import time

from treelib.node import *
from treelib import Ardennes

from datetime import datetime as dt
from multiprocessing import Process, Manager

from sklearn.metrics import confusion_matrix

from preprocessing.dataset import read_dataset, get_batch, get_fold_iter
from matplotlib import pyplot as plt

__author__ = 'Henry Cagnini'


def __clean_macros__(macros):
    for sets in macros.itervalues():
        os.remove(sets['train'])
        os.remove(sets['test'])
        if 'val' in sets:
            os.remove(sets['val'])


# noinspection PyUnresolvedReferences
def evaluate_j48(datasets_path, intermediary_path):
    # for examples on how to use this function, refer to
    # http://pythonhosted.org/python-weka-wrapper/examples.html#build-classifier-on-dataset-output-predictions
    import weka.core.jvm as jvm
    from weka.core.converters import Loader
    from weka.classifiers import Classifier
    from sklearn.metrics import precision_score, accuracy_score, f1_score

    from networkx.drawing.nx_agraph import graphviz_layout

    jvm.start()

    results = {
        'runs': {
            '1': dict()
        }
    }

    try:
        for dataset in os.listdir(datasets_path):
            dataset_name = dataset.split('.')[0]

            results['runs']['1'][dataset_name] = dict()

            loader = Loader(classname="weka.core.converters.ArffLoader")

            y_pred_all = []
            y_true_all = []
            heights = []

            for n_fold in it.count():
                try:
                    train_s = loader.load_file(os.path.join(intermediary_path, '%s_fold_%d_train.arff' % (dataset_name, n_fold)))
                    val_s = loader.load_file(os.path.join(intermediary_path, '%s_fold_%d_val.arff' % (dataset_name, n_fold)))
                    test_s = loader.load_file(os.path.join(intermediary_path, '%s_fold_%d_test.arff' % (dataset_name, n_fold)))

                    train_s.relationname = dataset_name
                    val_s.relationname = dataset_name
                    test_s.relationname = dataset_name

                    train_s.class_is_last()
                    val_s.class_is_last()
                    test_s.class_is_last()

                    warnings.warn('WARNING: appending validation set in training set.')
                    for inst in val_s:
                        train_s.add_instance(inst)

                    cls = Classifier(classname="weka.classifiers.trees.J48", options=["-C", "0.25", "-M", "2"])
                    cls.build_classifier(train_s)

                    warnings.warn('WARNING: will only work for binary splits!')
                    graph = cls.graph.encode('ascii')
                    out = StringIO.StringIO(graph)
                    G = nx.Graph(nx.nx_pydot.read_dot(out))

                    # TODO plotting!
                    # TODO plotting!
                    # TODO plotting!
                    # fig = plt.figure(figsize=(40, 30))
                    # pos = graphviz_layout(G, root='N0', prog='dot')
                    #
                    # edgelist = G.edges(data=True)
                    # nodelist = G.nodes(data=True)
                    #
                    # edge_labels = {(x1, x2): v['label'] for x1, x2, v in edgelist}
                    # node_colors = {node_id: ('#98FB98' if 'shape' in _dict else '#0099FF') for node_id, _dict in nodelist}
                    # node_colors['N0'] = '#FFFFFF'
                    # node_colors = node_colors.values()
                    #
                    # nx.draw_networkx_nodes(G, pos, node_color=node_colors)
                    # nx.draw_networkx_edges(G, pos, style='dashed', arrows=False)
                    # nx.draw_networkx_labels(G, pos, {k: v['label'] for k, v in G.node.iteritems()})
                    # nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)
                    # plt.axis('off')
                    # plt.show()
                    # exit(0)
                    # TODO plotting!
                    # TODO plotting!
                    # TODO plotting!

                    heights += [max(map(len, nx.shortest_path(G, source='N0').itervalues()))]

                    y_test_true = []
                    y_test_pred = []

                    # y_train_true = []
                    # y_train_pred = []

                    # for index, inst in enumerate(train_s):
                    #     y_train_true += [inst.get_value(inst.class_index)]
                    #     y_train_pred += [cls.classify_instance(inst)]

                    for index, inst in enumerate(test_s):
                        y_test_true += [inst.get_value(inst.class_index)]
                        y_test_pred += [cls.classify_instance(inst)]

                    y_true_all += y_test_true
                    y_pred_all += y_test_pred

                except Exception as e:
                    break

            results['runs']['1'][dataset_name] = {
                'confusion_matrix': confusion_matrix(y_true_all, y_pred_all).tolist(),
                'heights': heights,
            }

        json.dump(results, open('j48_results.json', 'w'), indent=2)

    finally:
        jvm.stop()


def evaluate_ardennes(datasets_path, config_file, output_path, validation_mode='cross-validation'):
    datasets = os.listdir(datasets_path)
    np.random.shuffle(datasets)  # everyday I'm shuffling

    print 'configuration file:'
    print config_file
    config_file['verbose'] = False

    n_runs = config_file['n_runs']

    # --------------------------------------------------- #
    # begin of {removes previous results, create folders}
    # --------------------------------------------------- #
    for i, dataset in enumerate(datasets):
        dataset_name = dataset.split('.')[0]

        if output_path is not None:
            dataset_output_path = os.path.join(output_path, dataset_name)

            if not os.path.exists(dataset_output_path):
                os.mkdir(dataset_output_path)
            else:
                shutil.rmtree(dataset_output_path)
                os.mkdir(dataset_output_path)
    # --------------------------------------------------- #
    # end of {removes previous results, create folders}
    # --------------------------------------------------- #

    dict_results = {'runs': dict()}

    for n_run in xrange(n_runs):
        dict_results['runs'][str(n_run)] = dict()

        for i, dataset in enumerate(datasets):
            dataset_name = dataset.split('.')[0]
            config_file['dataset_path'] = os.path.join(datasets_path, dataset)

            dataset_output_path = os.path.join(output_path, dataset_name)

            if output_path is not None:
                config_file['output_path'] = dataset_output_path
            try:
                dt_dict = do_train(
                    config_file=config_file,
                    evaluation_mode=validation_mode,
                    n_run=n_run
                )

                dict_results['runs'][str(n_run)][dataset_name] = dt_dict

                json.dump(dict_results, open(os.path.join(output_path, 'results.json'), 'w'), indent=2)
            except Exception as e:
                import warnings
                warnings.warn('Exception found when running %s!' % dataset)
                print(e.message, e.args)


def run_fold(n_fold, n_run, full, train_s, val_s, test_s, config_file, **kwargs):
    try:
        random_state = kwargs['random_state']
    except KeyError:
        random_state = None

    tree_height = config_file['tree_height']

    t1 = dt.now()

    with Ardennes(
        n_individuals=config_file['n_individuals'],
        decile=config_file['decile'],
        uncertainty=config_file['uncertainty'],
        max_height=tree_height,
        distribution=config_file['distribution'],
        n_iterations=config_file['n_iterations'],
        random_state=random_state
    ) as inst:
        inst.fit(
            full=full,
            train=train_s,
            val=val_s,
            test=test_s,
            verbose=config_file['verbose'],
            dataset_name=config_file['dataset_name'],
            output_path=config_file['output_path'] if 'output_path' in config_file else None,
            fold=n_fold,
            run=n_run,
            threshold_stop=config_file['threshold_stop'] if 'threshold_stop' in config_file else None,
        )

        ind = inst.best_individual
        y_test_pred = list(ind.predict(test_s))
        y_test_true = list(test_s[test_s.columns[-1]])

        t2 = dt.now()

    print 'Run %d of fold %d: Test acc: %02.2f Height: %d n_nodes: %d Time: %02.2f secs' % (
        n_run, n_fold, ind.test_acc_score, ind.height, ind.n_nodes, (t2 - t1).total_seconds()
    )

    if 'dict_manager' in kwargs:
        res = dict(
            y_test_pred=y_test_pred,
            y_test_true=y_test_true,
            height=ind.height,
            n_nodes=ind.n_nodes
        )

        kwargs['dict_manager'][n_fold] = res

    return ind.test_acc_score


def crunch_result_file(results_file, output_file=None):

    n_runs = len(results_file['runs'].keys())
    some_run = results_file['runs'].keys()[0]
    some_dataset = results_file['runs'][some_run].keys()[0]
    n_datasets = len(results_file['runs'][some_run].keys())
    n_folds = len(results_file['runs'][some_run][some_dataset]['folds'].keys())

    df = pd.DataFrame(
        columns=['run', 'dataset', 'fold', 'train_acc', 'val_acc', 'test_acc', 'test_precision', 'test_f1_score', 'height'],
        index=np.arange(n_runs * n_datasets * n_folds),
        dtype=np.object
    )

    dtypes = dict(
        run=np.float32, dataset=np.object, fold=np.float32,
        train_acc=np.float32, val_acc=np.float32, test_acc=np.float32,
        test_precision=np.float32, test_f1_score=np.float32, height=np.float32
    )

    for k, v in dtypes.iteritems():
        df[k] = df[k].astype(v)

    count_row = 0
    for n_run, run in results_file['runs'].iteritems():
        for dataset_name, dataset in run.iteritems():
            for n_fold, v in dataset['folds'].iteritems():
                train_acc = v['train_acc']
                val_acc = v['val_acc']
                test_acc = v['acc']
                precision = v['precision']
                _f1_score = v['f1_score']
                height = v['height']
                df.loc[count_row] = [
                    int(n_run), str(dataset_name), int(n_fold),
                    float(train_acc), float(val_acc), float(test_acc),
                    float(precision), float(_f1_score), float(height)
                ]
                count_row += 1

    print df

    grouped = df.groupby(by=['dataset'])['train_acc', 'val_acc', 'test_acc', 'test_precision', 'test_f1_score', 'height']
    final = grouped.aggregate([np.mean, np.std])

    print final

    if output_file is not None:
        final.to_csv(output_file, sep=',', quotechar='\"')


def crunch_evolution_data(path_results, criteria):
    df = pd.read_csv(path_results)
    for criterion in criteria:
        df.boxplot(column=criterion, by='iteration')
        plt.savefig(path_results.split('.')[0] + '_%s.pdf' % criterion, bbox_inches='tight', format='pdf')
        plt.close()


def generation_statistics(path_results):
    df = pd.read_csv(path_results)
    gb = df.groupby(by='iteration')
    meta = gb.agg([np.min, np.max, np.median, np.mean, np.std])
    meta.to_csv('iteration_statistics.csv')


def custom_pop_stat(general_path):
    datasets = [o for o in os.listdir(general_path) if os.path.isdir(os.path.join(general_path, o))]

    j = {'runs': {str(x): dict() for x in range(10)}}

    for dataset_name in datasets:
        for i in xrange(10):
            j['runs'][str(i)][dataset_name] = {'folds': {str(x): dict() for x in range(10)}}

        reports_full_path = os.path.join(general_path, dataset_name, '%s_evo_fold_[0-9]*_run_[0-9]*.csv' % dataset_name)
        reports = glob.glob(reports_full_path)

        for report in reports:
            info = report
            info = info.split('.')[0].split('/')[-1].replace('%s_evo_' % dataset_name, '')
            info = info.replace('fold_', '').replace('run_', '')
            fold, run = info.split("_")

            df = pd.read_csv(report)

            # TODO best test from last population
            # last_pop = df.loc[df['iteration'] == df['iteration'].max()]
            # best_fit = last_pop.loc[last_pop['validation accuracy'] == last_pop['validation accuracy'].max()]
            # best_from_all = best_fit.loc[best_fit['test accuracy'] == best_fit['test accuracy'].max()].iloc[0]
            # TODO best test from any generation
            # best_from_all = df.loc[df['test_acc'] == df['test_acc'].max()].iloc[0]
            # TODO best fitness from a given generation
            temp = df.loc[df['iteration'] == min(100, df['iteration'].max())]
            best_from_all = temp.loc[temp['fitness'] == temp['fitness'].max()].iloc[0]

            j['runs'][str(int(run))][dataset_name]['folds'][str(int(fold))] = {
                'train_acc': best_from_all['train_acc'],
                'val_acc': best_from_all['val_acc'],
                'acc': best_from_all['test_acc'],
                'precision': best_from_all['test_precision'],
                'f1_score': best_from_all['test_f1'],
                'height': best_from_all['height'],
                'n_nodes': best_from_all['n_nodes']
            }

    json.dump(j, open(os.path.join(general_path, 'new_results.json'), 'w'), indent=2)


def grid_optimizer(config_file, datasets_path, output_path):
    config_file['verbose'] = False

    range_individuals = [500]
    range_tree_height = [7]
    range_iterations = [100]
    range_decile = [.5, .95, .6, .8, .7, .9]
    n_runs = 10

    n_opts = reduce(
        op.mul, map(
            len,
            [range_individuals, range_tree_height, range_iterations, range_decile],
        )
    )

    count_row = 0

    for n_individuals in range_individuals:
        for tree_height in range_tree_height:
            for n_iterations in range_iterations:
                for decile in range_decile:

                    _partial_str = '[n_individuals:%d][n_iterations:%d][tree_height:%d][decile:%d]' % \
                                   (n_individuals, n_iterations, tree_height, int(decile * 100))

                    print 'opts: %02.d/%02.d' % (count_row, n_opts) + ' ' + _partial_str

                    _write_path = os.path.join(output_path, _partial_str)
                    if os.path.exists(_write_path):
                        shutil.rmtree(_write_path)
                    os.mkdir(_write_path)

                    config_file['n_individuals'] = n_individuals
                    config_file['n_iterations'] = n_iterations
                    config_file['tree_height'] = tree_height
                    config_file['decile'] = decile
                    config_file['n_runs'] = n_runs

                    evaluate_ardennes(
                        datasets_path=datasets_path,
                        config_file=config_file,
                        output_path=_write_path,
                        validation_mode='cross-validation'
                    )

                    count_row += 1

                    print '%02.d/%02.d' % (count_row, n_opts)


# noinspection PyUnresolvedReferences
def crunch_parametrization(path_file):
    import plotly.graph_objs as go
    from plotly.offline import plot

    full = pd.read_csv(path_file)  # type: pd.DataFrame
    df = full

    attrX = 'n_individuals'
    attrY = 'decile'
    attrZ = 'n_iterations'

    print 'attributes (x, y, z): (%s, %s, %s)' % (attrX, attrY, attrZ)

    trace2 = go.Scatter3d(
        x=df[attrX],
        y=df[attrY],
        z=df[attrZ],
        mode='markers',
        text=['%s: %2.2f<br>%s: %2.2f<br>%s: %2.2f<br>mean acc: %0.2f' %
              (attrX, info[attrX], attrY, info[attrY], attrZ, info[attrZ], info['acc mean']) for (index, info) in df.iterrows()
              ],
        hoverinfo='text',
        marker=dict(
            color=df['acc mean'],
            colorscale='RdBu',
            colorbar=dict(
                title='Mean accuracy',
            ),
            # cmin=0.,  # minimum color value
            # cmax=1.,  # maximum color value
            # cauto=False,  # do not automatically fit color values
            size=12,
            symbol='circle',
            line=dict(
                color='rgb(204, 204, 204)',
                width=1
            ),
            opacity=0.9
        )
    )
    layout = go.Layout(
        margin=dict(
            l=0,
            r=0,
            b=0,
            t=0
        ),
        scene=dict(
           xaxis=dict(title=attrX),
           yaxis=dict(title=attrY),
           zaxis=dict(title=attrZ)
        )
    )
    fig = go.Figure(data=[trace2], layout=layout)
    plot(fig, filename='parametrization.html')


def crunch_graphical_model(pgm_path, path_datasets):
    from networkx.drawing.nx_agraph import graphviz_layout
    import plotly.graph_objs as go
    from plotly.offline import plot

    def build_graph(series):
        G = nx.DiGraph()

        node_labels = dict()

        for node_id in xrange(series.shape[1]):
            probs = series[:, node_id]

            G.add_node(
                node_id,
                attr_dict=dict(
                    color=max(probs),
                    probs='<br>'.join(['%2.3f : %s' % (y, x) for x, y in it.izip(columns, probs)])
                )
            )
            parent = get_parent(node_id)
            if parent is not None:
                G.add_edge(parent, node_id)

            node_labels[node_id] = node_id

        return G

    def build_edges(_G):
        edge_trace = go.Scatter(
            x=[],
            y=[],
            line=go.Line(width=0.5, color='#999'),
            hoverinfo='none',
            mode='lines',
            name='edges'
        )

        for edge in _G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_trace['x'] += [x0, x1, None]
            edge_trace['y'] += [y0, y1, None]

        return edge_trace

    def build_nodes(_G, _generation):
        nodes = _G.nodes(data=True)

        _node_trace = go.Scatter(
            x=[pos[node[0]][0] for node in nodes],
            y=[pos[node[0]][1] for node in nodes],
            name='gen %d' % _generation,
            text=[x[1]['probs'] for x in nodes],
            mode='markers',
            visible=True if _generation == 0 else 'legendonly',
            hoverinfo='text',
            marker=go.Marker(
                showscale=True,
                color=[x[1]['color'] for x in nodes],
                colorscale='RdBu',
                colorbar=dict(
                    title='Assurance',
                    xpad=100,
                ),
                cmin=0.,  # minimum color value
                cmax=1.,  # maximum color value
                cauto=False,  # do not automatically fit color values
                reversescale=False,
                size=15,
                line=dict(
                    width=2
                )
            )
        )
        return _node_trace

    sep = '\\' if os.name == 'nt' else '/'

    dataset_name = pgm_path.split(sep)[-1].split('_')[0]

    dataset = read_dataset(os.path.join(path_datasets, dataset_name + '.arff'))
    columns = dataset.columns
    n_columns = dataset.shape[1]
    del dataset

    data = []

    with open(pgm_path, 'r') as f:
        csv_w = csv.reader(f, delimiter=',', quotechar='\"')
        for generation, line in enumerate(csv_w):
            series = np.array(line, dtype=np.float).reshape(n_columns, -1)  # each row is an attribute, each column a generation

            G = build_graph(series)

            pos = graphviz_layout(G, root=0, prog='dot')

            if generation == 0:
                data.append(build_edges(G))

            node_trace = build_nodes(G, generation)
            data += [node_trace]

        fig = go.Figure(
            data=go.Data(data),
            layout=go.Layout(
                title='Probabilistic Graphical Model<br>Dataset %s' % dataset_name,
                titlefont=dict(size=16),
                showlegend=True,
                hovermode='closest',

                xaxis=go.XAxis(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=go.YAxis(showgrid=False, zeroline=False, showticklabels=False),
            )
        )

        plot(fig, filename=pgm_path.split(sep)[-1] + '.html')


def do_train(config_file, n_run, evaluation_mode='cross-validation'):
    """

    :param config_file:
    :param n_run:
    :param evaluation_mode:
    :return:
    """

    assert evaluation_mode in ['cross-validation', 'holdout'], \
        ValueError('evaluation_mode must be either \'cross-validation\' or \'holdout!\'')

    dataset_name = config_file['dataset_path'].split('/')[-1].split('.')[0]
    config_file['dataset_name'] = dataset_name
    print 'training ardennes for %s' % dataset_name

    df = read_dataset(config_file['dataset_path'])
    random_state = config_file['random_state']

    if evaluation_mode == 'cross-validation':
        assert 'folds_path' in config_file, ValueError('Performing a cross-validation is only possible with a json '
                                                       'file for folds! Provide it through the \'folds_path\' '
                                                       'parameter in the configuration file!')

        result_dict = {'folds': dict()}

        folds = get_fold_iter(df, os.path.join(config_file['folds_path'], dataset_name + '.json'))

        manager = Manager()
        dict_manager = manager.dict()
        manager_output = manager.dict()

        processes = []

        for i, (train_s, val_s, test_s) in enumerate(folds):
            p = Process(
                target=run_fold, kwargs=dict(
                    n_fold=i, n_run=n_run, train_s=train_s, val_s=val_s,
                    test_s=test_s, config_file=config_file, dict_manager=dict_manager, random_state=random_state,
                    full=df, manager_output=manager_output
                )
            )
            p.start()
            processes.append(p)

        for p in processes:
            p.join()

        dict_results = dict(dict_manager)

        true = reduce(op.add, [dict_results[k]['y_test_true'] for k in dict_results.iterkeys()])
        pred = reduce(op.add, [dict_results[k]['y_test_pred'] for k in dict_results.iterkeys()])

        conf_matrix = confusion_matrix(true, pred)

        height = [dict_results[k]['height'] for k in dict_results.iterkeys()]
        n_nodes = [dict_results[k]['n_nodes'] for k in dict_results.iterkeys()]

        hit = np.diagonal(conf_matrix).sum()
        total = conf_matrix.sum()

        print 'acc: %0.2f  tree height: %02.2f +- %02.2f  n_nodes: %02.2f +- %02.2f' % (
            hit / float(total), float(np.mean(height)), float(np.std(height)), float(np.mean(n_nodes)), float(np.std(n_nodes))
        )

        return {
            'confusion_matrix': conf_matrix.tolist(),
            'height': height,
            'n_nodes': n_nodes
        }

    else:
        train_s, val_s, test_s = get_batch(
            df, train_size=config_file['train_size'], random_state=random_state
        )

        run_fold(
            n_fold=0, n_run=0, train_s=train_s, val_s=val_s,
            test_s=test_s, config_file=config_file, random_state=random_state,
            full=df
        )


def get_real_accuracy(_path_folds, result_file):
    files = os.listdir(_path_folds)

    all_results = pd.DataFrame(index=[x.split('.')[0] for x in files], columns=['test_accuracy_mean', 'test_accuracy_std'], dtype=np.float32)

    global_counter = 0
    for dataset in files:
        accs = []
        for n_run, run in result_file['runs'].iteritems():
            dataset_name = dataset.split('.')[0]
            fold_info = json.load(open(os.path.join(_path_folds, dataset), 'r'))
            real_accuracy = 0.
            total_size = 0
            for n_fold, index in fold_info.iteritems():
                try:
                    fold_accuracy = run[dataset_name]['folds'][n_fold]['acc']
                    size = len(index['test'])
                    total_size += size

                    real_accuracy += fold_accuracy * float(size)
                except KeyError:
                    pass

            try:
                accs += [real_accuracy / float(total_size)]
            except ZeroDivisionError:
                accs += [0.]

        all_results.iloc[global_counter] = [np.mean(accs), np.std(accs)]
        global_counter += 1
        # print 'dataset %s: %f +- %f' % (dataset_name, np.mean(accs), np.std(accs))

    print all_results
