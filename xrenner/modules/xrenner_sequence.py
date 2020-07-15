"""
modules/xrenner_sequence.py

Adapter class to accommodate sequence labeler
  * Supplies a uniform predict_proba() method
  * Reads serialized models
  * Compatible with flair embeddings

Author: Amir Zeldes
"""

import sys, os
from math import log
from collections import defaultdict

script_dir = os.path.dirname(os.path.realpath(__file__)) + os.sep

PY3 = sys.version_info[0] > 2

def featurize_conllu(conllu, feature_spec):
    class Token:
        def __init__(self, word="_", lemma="_", pos="_", func="_", parent="_", label="O"):
            self.word = word
            self.lemma = lemma
            self.pos = pos
            self.func = func
            self.parent = parent
            self.label = label

        def __repr__(self):
            return self.word + " (" + self.pos + "/" + self.func + ") = " + self.label

    def get_feats(prev_tok, tok, next_tok, specs):
        feat_dict = {"bias": 1.0}

        for key in specs:
            target = tok
            if "." in key:
                position, attr = key.split(".")
                if position == "next":
                    if next_tok.word == "_":
                        feat_dict["EOS"] = True
                        continue
                    else:
                        target = next_tok
                elif position == "prev":
                    if prev_tok.word == "_":
                        feat_dict["BOS"] = True
                        continue
                    else:
                        target = prev_tok
            else:
                attr = key
            if attr.startswith("lower"):
                feat_dict[key] = target.word.lower()
            elif attr in ["pos","lemma","func","parent"]:
                feat_dict[key] = getattr(target, attr)
            elif '[' in attr and ":" in attr:  # e.g. word[-2:] or prev.pos[:2]
                attr, offsets = attr.split("[")
                start, end = offsets.replace("]","").split(":")
                if len(start) > 0:
                    start = int(start)
                else:
                    start = 0
                if len(end) > 0:
                    end = int(end)
                else:
                    end = len(target.word)+1
                feat_dict[key] = getattr(target,attr)[start:end]
            else:
                sys.stderr.write("ERR: unknown sequencer feature:" + key + "!\n")
                quit()

        return feat_dict

    X = []
    y = []

    sents = conllu.strip().split("\n\n")
    for sent in sents:
        labels = []
        feats = []
        lines = sent.split("\n")
        toks = [Token()]  # Padding start token
        # Get parents
        sent_toks = {"0":"_"}
        for line in lines:
            if "\t" in line:
                tid, word, lemma, upos, xpos, morph, head, func, _, _ = line.split("\t")
                if "-" in tid:
                    continue
                sent_toks[tid] = word
        for line in lines:
            if "\t" in line:
                tid, word, lemma, upos, xpos, morph, head, func, _, _ = line.split("\t")
                if "-" in tid:
                    continue
                label = "O" if "ent_head=" not in morph else morph.replace("ent_head=", "")
                parent = sent_toks[head]
                toks.append(Token(word=word, lemma=lemma, pos=xpos, func=func, parent=parent, label=label))
                labels.append(label)
        toks.append(Token())  # Padding end token
        for i in range(1, len(toks) - 1):
            tok_feats = get_feats(toks[i - 1], toks[i], toks[i + 1], feature_spec)
            feats.append(tok_feats)

        X.append(feats)
        y.append(labels)
    return X, y


class StdOutFilter(object):
    def __init__(self):  # , strings_to_filter, stream):
        self.stream = sys.stdout
        self.stdout = sys.stdout

    def __getattr__(self, attr_name):
        return getattr(self.stream, attr_name)

    def write(self, data):
        output = []
        lines = data.split("\n")
        for line in lines:
            if "Epoch: " in line or (" f:" in line and "Test" not in line):
                output.append(line)
        if len(output) > 0:
            data = "\n".join(output) + "\n"
            self.stream.write("RNN log - " + data.strip() + "\n")
            self.stream.flush()

    def flush(self):
        pass
        # self.stream.flush()

    def start(self):
        sys.stdout = self

    def end(self):
        sys.stdout = self.stdout


class Token:
    def __init__(self, word="_", lemma="_", pos="_", func="_", parent="_", label="O"):
        self.word = word
        self.lemma = lemma
        self.pos = pos
        self.func = func
        self.parent = parent
        self.label = label

    def __repr__(self):
        return self.word + " (" + self.pos + "/" + self.func + ") = " + self.label


class Sequencer:
    def __init__(self, model_path=None, pickle=None):
        if model_path is None:
            model_path = (
                script_dir
                + ".."
                + os.sep
                + "models"
                + os.sep
                + "_sequence_taggers"
                + os.sep
                + "eng_flair_nner_distilbert.pt"
            )
        elif os.sep not in model_path:  # Assume this is a file in models/_sequence_taggers
            if pickle is None:
                model_path = script_dir + ".." + os.sep + "models" + os.sep + "_sequence_taggers" + os.sep + model_path
                if not os.path.exists(model_path):
                    sys.stderr.write("! Sequence tagger model file missing at " + model_path + "\n")
                    sys.stderr.write("! Add the model file or use get_models.py to obtain built-in models\nAborting...\n")
                    quit()

        if model_path.endswith(".crf"):  # Assume CRF Suite model
            from dill import load, loads
            if pickle is None:
                d = load(open(model_path, "rb"))
            else:
                from io import BytesIO
                d = loads(BytesIO(pickle.read()).read())

            self.tagger = d["model"]
            self.features = d["features"]
            self.model_type = "crfsuite"
        else:  # Assume flair model

            p = StdOutFilter()
            p.start()

            # Silently import flair/torch
            import flair
            from flair.data import Sentence
            from flair.models import SequenceTagger
            import torch

            p.end()

            self.tagger = SequenceTagger.load(model_path)
            self.model_type = "flair"

    def clear_embeddings(self, sentences, also_clear_word_embeddings=False):
        """
        Clears the embeddings from all given sentences.
        :param sentences: list of sentences
        """
        for sentence in sentences:
            sentence.clear_embeddings(also_clear_word_embeddings=also_clear_word_embeddings)

    def predict_proba(self, sentences):
        """
        Predicts a list of class and class probability tuples for every token in a list of sentences
        :param sentences: list of space tokenized sentence strings
        :return: the list of sentences containing the labels
        """
        output = []

        if self.model_type == "flair":
            # Sort sentences and keep order
            sents = [(len(s.split()), i, s) for i, s in enumerate(sentences)]
            sents.sort(key=lambda x: x[0], reverse=True)
            sentences = [s[2] for s in sents]

            preds = self.tagger.predict(sentences)

            if preds is None:  # Newer versions of flair have void predict method, use modified Sentence list
                preds = sentences

            # sort back
            sents = [tuple(list(sents[i]) + [s]) for i, s in enumerate(preds)]
            sents.sort(key=lambda x: x[1])
            sents = [s[3] for s in sents]

            for s in sents:
                for tok in s.tokens:
                    try:
                        label = tok.tags["ner"].value
                        score = tok.tags["ner"].score
                    except:
                        label = tok.labels[0].value
                        score = tok.labels[0].score
                    output.append(
                        (
                            label.replace("S-", "")
                            .replace("B-", "")
                            .replace("I-", "")
                            .replace("E-", ""),
                            score,
                        )
                    )
        elif self.model_type == "crfsuite":
            # sentences is assumed to contain conllu
            X, _ = featurize_conllu(sentences, self.features)
            preds = self.tagger.predict_marginals(X)
            for sent in preds:
                for tok in sent:
                    best = max(tok, key=tok.get)
                    output.append((best, tok[best]))  # output == [(best_label, score), ...]

        return output


if __name__ == "__main__":
    c = Sequencer()
    x = c.predict_proba(
        ["Mary had a little lamb", "Her fleece was white as snow .", "I joined Intel in the Age of Knives"]
    )
    print(x)