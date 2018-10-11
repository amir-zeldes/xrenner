# -*- coding: utf-8 -*-
import csv, ast, os
import numpy as np
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split
from sklearn import metrics
from matplotlib import pyplot as plt

path = "dump_files"
files = os.listdir(path)
vec = {'abstract': 1, 'person': 2, 'organization': 3, 'place': 4, 'time': 5, 'object': 6, 'event': 7, 'substance': 8,
       'quantity': 9, 'animal': 10, 'plant': 11, 'newspaper': 12}
X = []
y = []
for filename in files:
    file_train = csv.reader(open(path + '\\' + filename, 'r'))
    column = [row for row in file_train]
    for i, row in enumerate(column):
        if i == 0: continue
        headers = row[:]
        if headers[-1] == "_": continue
        # Morphological prediction
        morph_dict = ast.literal_eval(headers[-4])
        if 'abstract' in morph_dict.keys():
            morph_dict['abstract'] += 0.0000001
        if len(morph_dict) != 0:
            morph = vec[max(morph_dict.items(), key=lambda x: x[1])[0]]
        else:
            morph = 0
        # Dependency prediction
        dep_dict = ast.literal_eval(headers[-3])
        if 'abstract' in dep_dict.keys():
            dep_dict['abstract'] += 0.0000001
        if len(dep_dict) != 0:
            dep = vec[max(dep_dict.items(), key=lambda x: [1])[0]]
        else:
            dep = 0
        # Similarity-based prediction
        sim_dict = ast.literal_eval(headers[-2])
        if 'abstract' in sim_dict.keys():
            sim_dict['abstract'] += 0.0000001
        if len(sim_dict) != 0:
            sim = vec[max(sim_dict.items(), key=lambda x: x[1])[0]]
        else:
            sim = 0
        X.append([morph, dep, sim])
        y.append(vec[headers[-1]])

X = np.array(X)
y = np.array(y)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
svm = SVC()
svm.fit(X_train, y_train)
# svm.fit(X, y)
predicted = svm.predict(X_test)
print(metrics.classification_report(y_test, predicted))
