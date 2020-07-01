import warnings
import io, re, sys, os
import scipy.stats
from argparse import ArgumentParser
from glob import glob
from sklearn.metrics import make_scorer
from dill import dump

if sys.version_info[0] == 3 and sys.version_info[1] > 5:
    from sklearn.model_selection import RandomizedSearchCV
else:
    from sklearn.grid_search import RandomizedSearchCV

import sklearn_crfsuite
from sklearn_crfsuite import metrics

sys.path.append(os.sep.join(["..", "xrenner", "modules"]))
from xrenner_sequence import featurize_conllu

DEFAULT_FEATS = [
    "word.lower",
    "word[-3:]",
    "word[-2:]",
    "word[:3]",
    "word[:2]",
    "word.parent",
    "pos",
    "prev.lower",
    "prev.pos",
    "prev.pos[:2]",
    "prev.func",
    "prev.parent",
    "next.lower",
    "next.pos",
    "next.pos[:2]",
    "next.func",
]


def get_conll_data(train_path, test_path, do_shuffle=False, feat_spec=None):
    # X_train: a list sentences, each a list of word dictionaries, from feat to val (cat or num)
    # y_train: a list of sentences, each a list of label strings ('O', 'B-PER', 'person', whatever)
    train_conll = test_conll = ""
    files = []
    train_files = train_path.split(",")
    for f in train_files:
        files += glob(f)
    for f in files:
        train_conll += io.open(f, encoding="utf8").read()

    files = []
    test_files = test_path.split(",")
    for f in test_files:
        files += glob(f)
    for f in files:
        test_conll += io.open(f, encoding="utf8").read()

    if do_shuffle:
        from random import seed, shuffle

        seed(42)
        all_conll = train_conll + test_conll
        sents = all_conll.strip().split("\n\n")
        shuffle(sents)
        cutoff = int(len(sents) / 10)
        train_conll = "\n\n".join(sents[:-cutoff])
        test_conll = "\n\n".join(sents[-cutoff:])

    X_train, y_train = featurize_conllu(train_conll, feat_spec)
    X_test, y_test = featurize_conllu(test_conll, feat_spec)

    return X_train, y_train, X_test, y_test


def train(train_path, test_path, do_shuffle=False, feat_spec=None):
    if feat_spec is None:
        feat_spec = DEFAULT_FEATS

    crf = sklearn_crfsuite.CRF(
        algorithm="lbfgs",
        c1=0.3,  # 0.36418,#0.1,  ~~0.4
        c2=0.1,  # 0.03322,#0.1, ~~0.008
        max_iterations=100,
        min_freq=1,
        period=5,
        all_possible_transitions=True,
    )

    X_train, y_train, X_test, y_test = get_conll_data(train_path, test_path, do_shuffle, feat_spec)

    crf.fit(X_train, y_train)

    labels = list(crf.classes_)
    labels.remove("O")
    print(labels)

    y_pred = crf.predict(X_test)
    metrics.flat_f1_score(y_test, y_pred, average="weighted", labels=labels)

    # group B and I results
    sorted_labels = sorted(labels, key=lambda name: (name[1:], name[0]))
    print(metrics.flat_classification_report(y_test, y_pred, labels=sorted_labels, digits=3))

    return crf
    # crf.predict_marginals(X_test)


def crf_cross_val(train_path, test_path):

    X_train, y_train, X_test, y_test = get_conll_data(train_path, test_path)
    X_train += X_test
    y_train += y_test

    labels = list(set([l for s in y_test for l in s]))
    if "O" in labels:
        labels.remove("O")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        # define fixed parameters and parameters to search
        crf = sklearn_crfsuite.CRF(algorithm="lbfgs", max_iterations=100, all_possible_transitions=True)
        params_space = {
            "c1": scipy.stats.expon(scale=0.5),
            "c2": scipy.stats.expon(scale=0.05),
        }

        # use the same metric for evaluation
        f1_scorer = make_scorer(metrics.flat_f1_score, average="weighted", labels=labels)

        # search
        rs = RandomizedSearchCV(crf, params_space, cv=3, verbose=1, n_jobs=3, n_iter=15, scoring=f1_scorer)
        rs.fit(X_train, y_train)

        print("best params:", rs.best_params_)
        print("best CV score:", rs.best_score_)
        print("model size: {:0.2f}M".format(rs.best_estimator_.size_ / 1000000))


if __name__ == "__main__":

    p = ArgumentParser()
    p.add_argument("-m", "--mode", default="train", choices=["train", "crossval"])
    p.add_argument("--train_path", default="*train.conllu", help="glob pattern with conllu files to train on")
    p.add_argument("--test_path", default="*test.conllu", help="glob pattern with conllu files to test on")
    p.add_argument("--shuffle", action="store_true", help="use 10% shuffled sentences from training data as test data")
    p.add_argument("--model_path", default="model.crf", help="path to save trained model in train mode")
    opts = p.parse_args()

    feat_spec = DEFAULT_FEATS

    if opts.mode == "train":
        model = train(opts.train_path, opts.test_path, opts.shuffle, feat_spec)
        dump({"model": model, "features": feat_spec}, io.open(opts.model_path, "wb"))
    else:
        crf_cross_val(opts.train_path, opts.test_path)
