# -*- coding: utf-8 -*-
import csv, ast, os
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split
from sklearn import metrics

path = "dump_files"
files = os.listdir(path)
X = []
y = []
features_set = []
gold_set = []
feature_headers = ['docname', 'genre', 'n_lemma', 'n_func', 'n_head_text', 'n_form', 'n_pos', 'n_agree', 'n_start',
                   'n_end', 'n_cardinality', 'n_definiteness', 'n_entity', 'n_subclass', 'n_infstat', 'n_coordinate',
                   'n_length', 'n_mod_count', 'n_doc_position', 'n_sent_position', 'n_quoted', 'n_negated',
                   'n_neg_parent', 'n_s_type', 'morph_probs', 'dep_probs', 'sim_probs']

for filename in files:
    file_train = csv.reader(open(path + '\\' + filename, 'r'))
    for i, row in enumerate(file_train):
        if i == 0: continue
        headers = row[:]
        gold = headers[-1]
        if gold == "_": continue
        # Morphological prediction
        morph_dict = ast.literal_eval(headers[-4])
        if 'abstract' in morph_dict.keys():
            morph_dict['abstract'] += 0.0000001
        headers[-4] = max(morph_dict.items(), key=lambda x: x[1])[0] if len(morph_dict) != 0 else '_'
        # Dependency prediction
        dep_dict = ast.literal_eval(headers[-3])
        if 'abstract' in dep_dict.keys():
            dep_dict['abstract'] += 0.0000001
        headers[-3] = max(dep_dict.items(), key=lambda x: [1])[0] if len(dep_dict) != 0 else '_'
        # Similarity-based prediction
        sim_dict = ast.literal_eval(headers[-2])
        if 'abstract' in sim_dict.keys():
            sim_dict['abstract'] += 0.0000001
        headers[-2] = max(sim_dict.items(), key=lambda x: x[1])[0] if len(sim_dict) != 0 else '_'
        # Feature measurements
        features = {}
        if len(headers[:-1]) != len(feature_headers): assert False, "Length does not match."
        for n in range(len(headers[:-1])):
            features[feature_headers[n]] = headers[n]
        features_set.append(features)
        gold_set.append(headers[-1])

# Vectorize features
from sklearn.feature_extraction import DictVectorizer
vec = DictVectorizer()
X = vec.fit_transform(features_set).toarray()
from sklearn import preprocessing
le = preprocessing.LabelEncoder()
le.fit(gold_set)
y = le.transform(gold_set)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
svm = SVC(kernel='linear')
svm.fit(X_train, y_train)
predicted = svm.predict(X_test)
print(metrics.classification_report(y_test, predicted))
