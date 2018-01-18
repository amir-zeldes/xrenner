import pandas as pd
import numpy as np
import sys, re, os, io
from collections import defaultdict
from sklearn.preprocessing import LabelEncoder
from sklearn.preprocessing import LabelBinarizer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics import accuracy_score
from sklearn.externals.joblib import dump
from argparse import ArgumentParser, RawDescriptionHelpFormatter

"""
train_classifier.py

Example file for training classifiers on xrenner data. To build a classifier you will need to:

1. Run xrenner on your trainig data input (as conllx/conllu dependency files) and use the dump option (-d FILE)
2. Run utils/check_response.py on the dump file coupled with a gold coreference file in conll coreference format
3. Modify the code below to use the checked response file as training data for a classifier, typically using sklearn

Requirements: numpy, pandas, sklearn

See the xrenner documentation online for more information.
"""


# Error type costs if using sample_weights (should be tuned for training data; numbers from English OntoNotes)
# Initial values can be estimated using utils/get_decision_weights.py, then tuned as hyperparameters.
INVENT_ANA = 0.74
INVENT_ANTE = 0.78
INVENT_BOTH = 1.29
FALSE_NEW = 2.9
WRONG_LINK = 2.17

utils_dir = os.path.dirname(os.path.realpath(__file__))


example_text = "Example usage:\n\tpython make_classifier.py -t 10 -d 0.3 example_dump_response.tab"

parser = ArgumentParser(epilog=example_text, formatter_class=RawDescriptionHelpFormatter)
parser.add_argument("infile", help="Checked xrenner dump file with gold labels, created using utils/check_response.py")
parser.add_argument("-t","--thresh", type=int, default=0, help="Frequency threshold, replace rarer values by _unknown_")
parser.add_argument("-c","--criterion", type=float, default=0.5, help="Decision criterion boundary for classifier positive decision")
parser.add_argument("-d","--devset", default="dev_docs.tab", help="File listing dev set document names one per line")

options = parser.parse_args()

infile = options.infile

# Get list of documents names to use as held-out development data; if not provided, every 10th document is used instead
DEV_DOCS = []
if options.devset != "":
	DEV_DOCS = io.open(options.devset,encoding="utf8").read().strip().replace("\r","").split("\n")

if len(DEV_DOCS) == 0:
	sys.stderr.write("No development set found, using each 10th document as dev set")

### CLASSES ###


class DataFrameSelector(BaseEstimator, TransformerMixin):
	"""Selects columns to include from a pandas DataFrame"""

	def __init__(self, attribute_names):
		self.attribute_names = attribute_names
	def fit(self, X, y=None):
		return self
	def transform(self, X):
		return X[self.attribute_names].values


class HeuristicClassifier:
	"""
	Dummy classifier predicting whatever the first column in its input matrix contains (0 or 1)
	Used to evaluate performance of xrenner's default heuristic, in the heuristic_score column of xrenner dumps
	"""
	def __init__(self):
		pass

	def predict(self, x_test):
		predictions = []
		for i, x in enumerate(x_test):
			if x[0] == 1.0:
				predictions.append(1.0)
			else:
				predictions.append(0.0)
		return np.array(predictions)

	def predict_proba(self, x_test):
		predictions = []
		for i, x in enumerate(x_test):
			if x[0] == 1.0:
				predictions.append(1.0)
			else:
				predictions.append(0.0)
		return np.array(predictions)

########

def remove_rare(dataset, cols, thresh):
	"""
	Function to remove rare values from selected columns of a DataFrame (currently a single threshold is used for all columns)

	:param dataset: a pandas DataFrame
	:param cols: list of column names
	:param thresh: frequency below which values are replaced with _unknown_ (same label as OOV items at test time)
	:return: None (DataFrame is modified in place)
	"""
	if thresh > 0:
		for col in cols:
			dataset.loc[dataset[col].value_counts()[dataset[col]].values < options.thresh, col] = "_unknown_"
		sys.stderr.write("Removed values less frequent than " + str(thresh) + "\n")


def eval_estimator(estimator, X, y, pipeline=None, name="anon_estimator", cohort_eval=False, cohort_stats=False, pred_file=None):
	"""
	Function to evaluate a trained estimator on some data

	:param estimator: An estimator object with .predict() and .predict_prob() methods
	:param X: A pandas DataFrame with training data or a 2D numpy numeric array
	:param y: A single column DataFrame with binary data: coref or no coref
	:param pipeline: A Pipeline object with a .transform() method to turn a pandas X input into a numeric numpy array
	:param name: A name to use for this classifier verbose output
	:param cohort_eval: Whether to perform cohort based evaluation (i.e. how many anaphors got the right antecedent: each anaphor is one cohort)
	:param cohort_stats: Whether to output stats about cohorts in the gold training data
	:param pred_file: If a file path is supplied, predictions will be written to this file
	:return: None
	"""

	if pipeline is not None:
		test_X = pipeline.transform(X)
	else:
		test_X = X

	pred = estimator.predict(test_X)

	clf_type, _ = get_clf_type(estimator)

	if clf_type == "decision":
		d = estimator.decision_function(test_X)
		scores = np.exp(d) / (1 + np.exp(d))
	elif clf_type == "tuple":
		probas = estimator.predict_proba(test_X)
		scores = [tpl[1] for tpl in probas]
	else:
		scores = estimator.predict_proba(test_X)

	if pred_file is not None:
		with open(pred_file,'w') as f:
			f.write("\n".join([str(x) for x in pred])+"\n")

	acc = accuracy_score(y, pred)

	max_scores = defaultdict(float)
	solvable = set([])
	correct = set([])
	correct_dummy = set([])
	target_is_dummy_cohorts = set([])
	correct_in_solvable = set([])
	correct_dummy_in_solvable = set([])
	all_cohorts = set([])

	entries = X.shape[0]

	if cohort_eval or cohort_stats:
		j = -1
		for i, row in X.iterrows():
			j += 1
			score = scores[j]  # Single float as positive probability
			bin_resp = y.loc[i]
			cohort = row['cohort_id']
			is_new = row['n_first_mention']

			all_cohorts.add(cohort)
			if bin_resp == 1:
				solvable.add(cohort)

			if score > max_scores[cohort]:
				max_scores[cohort] = score
				if bin_resp == 1:
					correct.add(cohort)
				else:
					if cohort in correct:
						correct.remove(cohort)
						if cohort in correct_dummy:
							correct_dummy.remove(cohort)
			if is_new:
				target_is_dummy_cohorts.add(cohort)

			if max_scores[cohort] < options.criterion:
				if cohort not in solvable:
					solvable.add(cohort)
					correct.add(cohort)

			for cohort in target_is_dummy_cohorts:
				if cohort in correct:
					correct_dummy.add(cohort)

		for cohort in solvable:
			if cohort in correct:
				correct_in_solvable.add(cohort)
			if cohort in correct_dummy:
				correct_dummy_in_solvable.add(cohort)

		cohorts = len(max_scores)

	if cohort_stats:
		print("Cohort stats:\n" + "="*20)
		print("\tProcessed " + str(entries) + " entries")
		print("\tCohorts in data: " + str(cohorts))
		print("\tMean cohort size: " + str(entries / cohorts))
		print("\tTotal new: " + str(len(target_is_dummy_cohorts)))
		print("\tSolvable: " + str(len(solvable)) + " (" + str(100*len(solvable) / cohorts) + "%)")

	print("\nReport for " + name + ": \n" + "="*20)
	print("\to Held-out accuracy: " + str(100*acc) + "%")

	if cohort_eval:
		print("\to Cohort accuracy: " + str(100*len(correct) / cohorts)+"%")
		print("\to Correct within solvable: " + str(len(correct_in_solvable)) + " (" + str(
			100 * len(correct_in_solvable) / len(solvable)) + "%)")
		print("\to Correct new within new: " + str(len(correct_dummy)) + " (" + str(
			100 * len(correct_dummy) / len(target_is_dummy_cohorts)) + "%)")


def get_clf_type(clf):
	"""
	Function to determine how a classifier's .predict_proba() equivalent method is accessed
	and how feature importances are retrieved.

	:param clf: A classifier object
	:return: tuple of a predict_proba style, e.g. 'decision' function, 'tuple' of class probabilities, or p(positive)
			 and a importances type, e.g. 'importances', 'coef' or 'none'
	"""

	type_string = str(type(clf))
	re_decision = re.compile(r"Ridge|Elastic|Logistic")
	re_tuple = re.compile(r"StochasticGradient|MultilayerPercep|RandomForest|ExtraTrees|Dummy|Boost")

	if re_decision.search(type_string) is not None:
		return "decision", "coef" # The classifier uses a decision function, use exp to get probabilities
	elif re_tuple.search(type_string) is not None:
		if "Forest" in type_string or "ExtraTrees" in type_string or "Boost" in type_string:
			return "tuple", "importances"  # The predict_proba method returns an iterable where index 1 is p(positive_class)
		else:
			return "tuple", "none"
	else:
		return "proba", "none"  # Otherwise predict_proba() returns p(positive_class)


def make_clf(clf, clf_data, dump_name, float_labels, scale_labels, hot_labels, ord_labels,
			 use_weights=False, print_importances=True, cohort_eval=True, cohort_stats=True,do_dump=True,
			 prepare_only=False,refit_all=False,num_folds=3):
	"""

	:param clf: A classifier object using sklearn's API (e.g. supports .fit(X,y), .predict(X), .predict_proba(X))
	:param clf_data: A pandas DataFrame
	:param dump_name: String name to use for the classifier file when it is pickled and dumped via joblib
	:param float_labels: List of column names containing floats as-is
	:param scale_labels: List of column names containing numerical data to be standard-scaled (critical for DNNs, e.g. MLP)
	:param hot_labels: List of column names to transform into one-hot arrays (important for linear models with categorical variables)
	:param ord_labels: List of column names with categorical features to be replaced by arbitrary numbers (useful for RandomForest, GradientBoosting and similar)
	:param use_weights: (optional) Whether to use distinct error weights for error types such as Wrong Link, False New, etc.
	:param print_importances: (optional) Whether to print variable importances, if clf supports them
	:param cohort_eval: (optional) Whether to print just raw row-wise accuracy, or also analyze cohort statistics (how many anaphors resolved correctly)
	:param cohort_stats: (optional) Whether to print statistics for cohorts in the test data (usually used only on first classfier trained in a run)
	:param do_dump: (optional) Whether to dump a classifier file for xrenner
	:param prepare_only: (optional) Does not actually run the classifier, instead prepares the data and returns it to the main function
	:param refit_all: (optional) Whether to refit the classifier on all data (train+dev) after evaluation and use this fit for the dump
	:param num_folds: (optional) Number of folds to use when 'prepare_only' is used to create predetermined k-folds for cross-validation
	:return: None, or if 'prepare_only', the transformed X matrix, y response and k-fold information to use in a grid search
	"""

	clf_type, importance_type = get_clf_type(clf)

	encoders = {}
	binarizers = {}
	scalers = {}

	num_labels = float_labels + scale_labels

	for cat in ord_labels:
		encoder = LabelEncoder()
		with_unknown = pd.Series(np.concatenate((clf_data.loc[:, cat], ["_unknown_"])))
		encoder.fit(with_unknown)
		encoded = encoder.transform(clf_data.loc[:, cat])
		clf_data[cat] = encoded
		encoders[cat] = (encoder, "encoder", set(encoder.classes_))

	new_hot_labels = set([])
	for cat in hot_labels:
		encoder = LabelBinarizer()
		with_unknown = pd.Series(np.concatenate((clf_data.loc[:, cat], ["_unknown_"])))
		encoder.fit(with_unknown)
		encoded = encoder.transform(clf_data.loc[:, cat])

		# TODO: deal with two class case, when sklearn makes the hot label be a single column (0 vs 1)
		for i, col_val in enumerate(encoder.classes_):
			new_label = cat + "_" + col_val
			clf_data[new_label] = encoded[:, i]
			new_hot_labels.add(new_label)
		binarizers[cat] = (encoder, "binarizer", set(encoder.classes_))

	new_hot_labels = list(new_hot_labels)

	cat_labels = ord_labels + hot_labels

	# Get all doc names
	docs = sorted(list(clf_data["doc_id"].unique()))

	train_docs = set([])
	test_docs = set([])
	doc_sets = defaultdict(list)  # Holds predetermined reproducible document-wise folds in 3-fold cross-validation
	j = -1
	for i, doc in enumerate(docs):
		j += 1
		if j > num_folds - 1:
			j = 0
		if len(DEV_DOCS) == 0:
			if i % 10 == 0:
				test_docs.add(doc)
			else:
				train_docs.add(doc)
		else:
			if doc in DEV_DOCS:
				test_docs.add(doc)
			else:
				train_docs.add(doc)
		doc_sets[j].append(doc)

	if test_docs == [] and len(DEV_DOCS) > 0:
		sys.stderr.write("No dev set documents found in input file\nQuitting...\n")
		sys.exit()

	sys.stderr.write("Finished splitting by document...\n")

	train_index = clf_data.index[clf_data['doc_id'].isin(train_docs)]
	test_index = clf_data.index[clf_data['doc_id'].isin(test_docs)]

	train_set = clf_data.loc[train_index]
	test_set = clf_data.loc[test_index]


	if use_weights:
		weights = np.where(train_set["bin_resp"] == 0,
						   		np.where(train_set["ana_miss"],
										 np.where(train_set["ante_miss"],INVENT_BOTH,INVENT_ANA),
										 np.where(train_set["ante_miss"], INVENT_ANTE,WRONG_LINK)),
								FALSE_NEW)

	new_train = train_set.copy()
	new_test = test_set.copy()

	for cat in scale_labels:
		scaler = StandardScaler()
		scalers[cat] = scaler
		new_train[cat] = scaler.fit_transform(train_set[cat].values.reshape(-1, 1))
		new_test[cat] = scaler.transform(test_set[cat].values.reshape(-1, 1))
		if cat in float_labels:
			float_labels.remove(cat)
		scalers[cat] = (scaler, "scale", None)

	train_set = new_train
	test_set = new_test

	print("After transforms, X matrix has "+str(train_set.shape[1])+" columns")

	cat_pipeline = Pipeline([('selector', DataFrameSelector(ord_labels + new_hot_labels))])
	num_pipeline = Pipeline([('selector', DataFrameSelector(num_labels))])
	preparation_pipeline = FeatureUnion(transformer_list=[("num_pipeline", num_pipeline),("cat_pipeline", cat_pipeline)])

	sys.stderr.write("Preparing X matrix...\n")

	all = pd.concat([train_set,test_set])
	folds = []
	for i, row in all.iterrows():
		for j in doc_sets:
			if row["doc_id"] in doc_sets[j]:
				folds.append(j)
				break

	X = preparation_pipeline.fit_transform(train_set)
	X_test = preparation_pipeline.fit_transform(test_set)
	y = train_set["bin_resp"]
	y_test = test_set["bin_resp"]

	# Used if we are not actually training yet, just preparing the data, folds etc.
	if prepare_only:
		return np.concatenate([X,X_test]), np.concatenate([y,y_test]), folds


	sys.stderr.write("\nTraining " + dump_name +"...\n")
	if use_weights:
		clf.fit(X, y,sample_weight=weights)
	else:
		clf.fit(X, y)

	if print_importances:
		if importance_type == "none":
			print("Can't retrieve feature importances for " + dump_name + "\n")
		else:
			print("\nFeature importances:")
			feature_names = num_labels + ord_labels + new_hot_labels
			if importance_type == "importances":
				importances = clf.feature_importances_
			else:
				importances = clf.coef_[0]

			zipped = zip(feature_names, importances)
			sorted_zip = sorted(zipped, key=lambda x: x[1], reverse=True)
			for name, importance in sorted_zip:
				print(name, "=", importance)
		print("")

	eval_estimator(clf, test_set, y_test, name=dump_name, pipeline=preparation_pipeline, cohort_eval=cohort_eval, cohort_stats=cohort_stats)

	if refit_all:
		X_all = np.concatenate([X, X_test])
		y_all = np.concatenate([y, y_test])
		clf.fit(X_all,y_all)

	if do_dump:
		encoders.update(binarizers)
		encoders.update(scalers)
		xrenner_clf = (clf, encoders, num_labels + cat_labels)
		dump(xrenner_clf, dump_name + '.pkl', compress=3, protocol=2)
		print("Dumped classifier file to disk: " + dump_name + ".pkl\n")


sys.stderr.write("Reading training file...\n")

df = pd.read_csv(infile,sep="\t", encoding="utf8", quoting=3, na_filter=False, keep_default_na=False)


#### Constructing a classifier ####

# These are just examples - any classifier implementing .fit(X,y) .predict_proba() and .predict() may be used
# Different classifiers can be used for different matching rules in config.ini, and separate versions can be
# used to support Python 2 and 3 (see online documentation)
#
# We can divide xrenner dump columns into:
#  * float_labels - raw numerical predictors (usually fine for scaling invariant classifiers, e.g. RandomForest)
#  * scale_labels - numerical predictors to be fed into a stadard scaler (e.g. for a scaling sensitive neural network)
#  * ord_labels - categorical predictors, each value is converted to some integer (often combined with the --thresh option)
#  * hot_labels - categorical predictors, converted to a one-hot binary array (better for neural networks, linear models)
#
# Let's build a RandomForestClassifiers for pronouns and a GradientBoostingClassifier for lexical NPs
# (not necessarily a realistic scenario)


# We copy the data in case we want different transformations later
data = df.copy()

# Let's separate the pronouns in the dump
pron_idx = data.index[df['n_form'].isin(['pronoun'])]
non_pron_data = data.loc[~data.index.isin(pron_idx)].copy()
pron_data = data.loc[pron_idx].copy()

# Let's get a majority baseline on pronoun classification
from sklearn.dummy import DummyClassifier

# The dummy classifier needs one column to function, but doesn't use any predictors
float_labels, scale_labels, hot_labels, ord_labels = ["d_tok"],[],[],[]
d = DummyClassifier(strategy="most_frequent")
# Evaluate and get cohort stats, but no need to dump
make_clf(d, pron_data, "majority_baseline", float_labels, scale_labels, hot_labels, ord_labels, cohort_eval=True, cohort_stats=True, do_dump=False)


# Now a more useful one, which we can dump to disk
# Select some columns and decide how to encode them
float_labels = ["d_sametext","n_quoted","t_quoted","d_speaker","d_sent", "d_intervene", "d_cohort", "d_entidep", "d_lexdep", "d_tok", "n_doc_position", "t_sent_position", "t_mod_count", "d_entisimdep", "t_length"]
scale_labels = []
hot_labels = []
ord_labels = ["n_lemma","n_agree","genre","n_entity","t_agree","t_entity","t_form","t_func","t_infstat","t_pos"]

# Replace rare values with "_unknown_"
if options.thresh > 0:
	remove_rare(pron_data, ord_labels + hot_labels, options.thresh)

# Let's get a baseline on how well xrenner's heuristic handled these pronouns (the heuristic_score column)
h = HeuristicClassifier()
p = Pipeline([('selector', DataFrameSelector(["heuristic_score","cohort_id"]))])
eval_estimator(h, data, data["bin_resp"], name="heuristic", pipeline=p, cohort_eval=True)

# OK, now to train a RandomForestClassifier:
from sklearn.ensemble import RandomForestClassifier
rf_pron = RandomForestClassifier(random_state=42, n_jobs=-1, n_estimators=60, max_features=7)
make_clf(rf_pron,pron_data, "rf_pron", float_labels, scale_labels, hot_labels, ord_labels, cohort_eval=True)

# Let's make a separate GradientBoostingClassifier for the lexical NPs now
# Choose different predictors:
float_labels = ["n_neg_parent","t_neg_parent","d_sametext","n_quoted","t_quoted","d_speaker","d_sent", "d_intervene", "d_cohort", "d_entidep", "d_lexdep", "d_tok", "n_doc_position", "t_sent_position", "t_mod_count", "d_entisimdep", "t_length","d_samelemma", "n_sent_position", "t_doc_position", "n_length"]
ord_labels = ["n_agree","n_form","n_func","n_entity","t_agree","t_entity","t_form","t_func","t_pos","t_definiteness"]

# Note you may want to use different thresholds, and you can also call remove_rare multiple times on different column lists
remove_rare(non_pron_data, ord_labels + hot_labels, thresh=10)

# We can use any classifier we like it if supports .fit() and .predict()+.predict_proba().
# Gradient boosting also supports sample_weights, so we can use use_weights in make_clf
from sklearn.ensemble import GradientBoostingClassifier
gbm_lex = GradientBoostingClassifier(random_state=42, max_features=7, learning_rate=0.1, n_estimators=100, max_depth=20,
									 min_samples_split=500, min_samples_leaf=50, subsample=0.8)
make_clf(gbm_lex, non_pron_data, "gbm_lex", float_labels, scale_labels, hot_labels, ord_labels, use_weights=True)

# Finally if you'd like to cross validate and search for optimal hyperparameters, you can use GridSearchCV
# Using pre-defined splits is crucial, since row-wise random dev sets will contain items from the same
# cohorts as the training set (antecedent suggestions for the same anaphors). Using folds from make_clf,
# dev data always comes from totally separate documents, preventing overfitting.

from sklearn.model_selection import GridSearchCV, PredefinedSplit
from sklearn.neural_network import MLPClassifier

mlp_pron = MLPClassifier(random_state=42, max_iter=300)

float_labels = ["d_sametext","n_quoted","t_quoted","d_speaker", "n_doc_position", "t_sent_position"]
scale_labels = ["d_sent", "d_intervene", "d_cohort", "d_entidep", "d_lexdep", "d_tok", "t_mod_count", "d_entisimdep", "t_length"]
ord_labels = []
hot_labels = ["n_lemma","n_agree","n_entity","t_agree","t_entity","t_form","t_func","t_pos"]

X, y, folds = make_clf(mlp_pron, pron_data, "mlp_pron", float_labels, scale_labels, hot_labels, ord_labels, prepare_only=True)

hyper_params = [{"hidden_layer_sizes":[(50,15),(75,25)],"activation":["tanh","relu"]}]

pre_folds = PredefinedSplit(np.array(folds))
grid = GridSearchCV(mlp_pron, param_grid=hyper_params, refit=False, cv=pre_folds, return_train_score=True)
grid.fit(X,y)
print("\nGrid search results:\n" + 30*"=")
for key in grid.cv_results_:
	print(key + ": " + str(grid.cv_results_[key]))

print("\nBest parameters:\n" + 30*"=")
print(grid.best_params_)

