#!/usr/bin/python
# -*- coding: utf-8 -*-

import pandas as pd
import subprocess
import tempfile, re, os, io
import sys
from collections import defaultdict
from argparse import ArgumentParser

"""
get_decision_weights.py

Script that takes an xrenner dump file and gold coreference data in the conll format, and sequentially tests the effects
of getting each prediction wrong on the official conll scorer's metrics. Requires the path to the conll scorer to be
set. The conll gold coreference format should look like this:

# begin document DOCNAME
0	The	(1
1	woman	1)
2	saw	_
3	herself	(1)
...

Script output looks like this - for each prediction in the dump file, the error type and cost for each metric is given,
as well as the antecedent's gold chain size (0 if the antecedent is not in the gold file)

f	muc	bcub	ceafe	size	type
0.676666666667	0.79	1.1	0.14	15	false_neg
1.67666666667	0.79	1.99	2.25	15	false_neg
...

Average weights per error type can be used as baselines for hyperparameter optimizations in utils/train_classifier.py
"""


def exec_via_temp(input_text, command_params, workdir=""):
	temp = tempfile.NamedTemporaryFile(delete=False)
	exec_out = ""
	try:
		if sys.version_info[0] < 3:
			temp.write(input_text)
		else:
			temp.write(input_text.encode("utf8"))
		temp.close()

		command_params = [x if x != 'tempfilename' else temp.name for x in command_params]
		if workdir == "":
			proc = subprocess.Popen(command_params, stdout=subprocess.PIPE,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
			(stdout, stderr) = proc.communicate()
		else:
			proc = subprocess.Popen(command_params, stdout=subprocess.PIPE,stdin=subprocess.PIPE,stderr=subprocess.PIPE,cwd=workdir)
			(stdout, stderr) = proc.communicate()

		exec_out = stdout
	except Exception as e:
		print(e)
	finally:
		os.remove(temp.name)
		if sys.version_info[0] < 3:
			return exec_out
		else:
			return exec_out.decode("utf8")


def read_gold(gold_str, target_doc):
	docname = ""
	open_marks = {}
	marks_by_end = {}  # Needed for tracking apposition envelopes
	marks_by_start = {}
	marks = {}
	is_first = {}

	groups2ids = defaultdict(list)
	group_freqs = defaultdict(int)
	tokens = []

	opening_marks = defaultdict(list)
	closing_marks = defaultdict(list)
	single_marks = defaultdict(list)

	is_target = False

	for line in gold_str.split("\n"):
		fields = line.split("\t")
		if len(fields) > 0:
			if fields[0].startswith("# begin"):
				if is_target:  # Target was already found
					break
				m = re.search("# begin document ([^\s]+)", fields[0])
				docname = m.group(1)
				if docname == target_doc:
					is_target = True
				else:
					is_target = False
				doc_start = m.group(0)
				is_first[docname] = {}
				open_marks[docname] = {}
				marks_by_start[docname] = defaultdict(list)
				marks_by_end[docname] = defaultdict(list)
			elif len(fields) > 2 and is_target:
				tokens.append(fields[1])
				coref = fields[-1]
				if coref != "_":
					open_matches = re.findall(r'\(([0-9]+)', coref)
					for match in open_matches:
						open_marks[docname][match] = fields[0]
					close_matches = re.findall(r'([0-9]+)\)', coref)
					for match in close_matches:
						if match not in open_marks[docname]:
							sys.stderr.write("Unopened mark closed: doc " + docname + " tok " + fields[0] + "\n")
							sys.exit()
						marks[open_marks[docname][match] + "-" + fields[0]] = match
						marks_by_end[docname][fields[0]].append((match, open_marks[docname][match], fields[0]))
						marks_by_start[docname][open_marks[docname][match]].append((match, open_marks[docname][match], fields[0]))
						group_freqs[match] += 1
						groups2ids[match].append(open_marks[docname][match] + "-" + fields[0])

						if open_marks[docname][match] == fields[0]:
							single_marks[fields[0]].append(match)
						else:
							opening_marks[open_marks[docname][match]].append(match)
							closing_marks[fields[0]].append(match)

	return tokens, marks, group_freqs, opening_marks, closing_marks, single_marks, doc_start


def rem_singletons(file_string):

	out_str = ""
	freqs = defaultdict(int)

	lines = file_string.split("\n")

	for line in lines:
		if "\t" in line:
			fields = line.split("\t")
			coref = fields[-1]
			open_matches = re.findall(r'\(([0-9]+)', coref)
			for match in open_matches:
				freqs[match] += 1
			close_matches = re.findall(r'(?:^|[^(0-9])([0-9]+)\)', coref)
			for match in close_matches:
				freqs[match] += 1

	to_delete = set([])

	for match in freqs:
		if freqs[match] == 1:
			to_delete.add(match)

	for line in lines:
		if "\t" in line:
			out_coref = ""
			fields = line.split("\t")
			if fields[0] == "647":
				a=5
			coref = fields[-1]
			sg_matches = re.findall(r'\(([0-9]+)\)', coref)
			for match in sg_matches:
				if match not in to_delete:
					out_coref += "(" + match + ")"
				coref = coref.replace("(" + match + ")","")
			open_matches = re.findall(r'\(([0-9]+)(?!\))', coref)
			for match in open_matches:
				if match not in to_delete:
					out_coref += "(" + match
				coref = coref.replace("(" + match + ")","")
			close_matches = re.findall(r'(?<!\()([0-9]+)\)', coref)
			for match in close_matches:
				if match not in to_delete:
					out_coref += match + ")"
				coref = coref.replace(match + ")","")
			if out_coref == "":
				out_coref = "_"
			fields[-1] = out_coref
			out_str += "\t".join(fields) + "\n"
		else:
			out_str += line + "\n"

	return out_str


def set_group(tokens, ana_id, new_group, opening_marks, closing_marks, single_marks, ante_id="", ana_group=""):

	out_str = ""
	ana_start, ana_end = ana_id.split("-")
	if ante_id != "":
		ante_start, ante_end = ante_id.split("-")
	else:
		ante_start, ante_end = "__", "__"
	after = False
	found = False

	for i, tok in enumerate(tokens):
		if i > int(ana_end):
			after = True  # We are after the changed markable

		coref = ""

		# Single token mark case
		if str(i) in single_marks:
			for mark in single_marks[str(i)]:
				if not after:
					if ana_id != str(i) + "-" + str(i):
						coref += "(" + mark + ")"
					else:
						ana_group = mark  # Redundant?
						coref += "(" + new_group + ")"
						found = True
				else:
					if mark != ana_group:
						coref += "(" + mark + ")"
					else:
						coref += "(" + new_group + ")"

		# Closing case
		if str(i) in closing_marks:
			for mark in closing_marks[str(i)]:
				if not after:
					if not (ana_end == str(i) and mark == ana_group):
						coref += mark + ")"
					else:
						coref += new_group + ")"
						found = True
				else:
					if mark != ana_group:
						coref += mark + ")"
					else:
						coref += new_group + ")"

		# Opening case
		if str(i) in opening_marks:
			for mark in opening_marks[str(i)]:
				if not after:
					if not (ana_start == str(i) and mark == ana_group):
						coref += "(" + mark
					else:
						coref += "(" + new_group
						found = True
				else:
					if mark != ana_group:
						coref += "(" + mark
					else:
						coref += "(" + new_group

		# Invented markable cases
		if not found:
			if str(i)== ana_start and str(i) == ana_end:  # Invented single token markable
				coref += "(" + new_group + ")"
			else:
				if str(i)== ana_start:
					coref += "(" + new_group
				elif str(i)== ana_end:
					if coref != "" and not coref.endswith(")"):
						coref += "|"
					coref += new_group + ")"

			if str(i)== ante_start and str(i) == ante_end:  # Invented single token markable
				coref += "(" + new_group + ")"
			else:
				if str(i)== ante_start:
					coref += "(" + new_group
				elif str(i)== ante_end:
					if coref != "" and not coref.endswith(")"):
						coref += "|"
					coref += new_group + ")"

		if coref == "":
			coref = "_"

		out_str += str(i) + "\t" + tok + "\t" + coref + "\n"

	return out_str


def parse_report(report):
	matches = re.findall(r'Coreference: Recall: [^\n]+F1: ([0-9]+\.?[0-9]*)%',report)
	fs = []

	for i, match in enumerate(matches):
		if i in [0,1,3]:
			fs.append(float(match))

	return [sum(fs)/3.0] + fs


parser = ArgumentParser()
parser.add_argument("infile", default="example_dump_response.tab", help="Dump file with checked xrenner predictions to get costs for")
parser.add_argument("goldfile", default="example_gold.conll", help="File with gold coreference data in conll format")
parser.add_argument("-d","--docname",action="store", default=None ,help="Document name to check; first document found if None")
parser.add_argument("-r","--remove_singletons",action="store_true",help="Whether singletons are removed in testing (e.g. for OntoNotes)")

options = parser.parse_args()

df = pd.read_csv(options.infile,sep="\t", encoding="utf8", quoting=3, na_filter=False, keep_default_na=False)

gold=io.open(options.goldfile,encoding="utf8").read()

scorer = "scorer.pl"  # Path to scorer script, or scorer.bat for Windows

if not os.path.isfile(scorer):
	print("Coreference scorer not found at " + scorer)
	print("You can download the scorer from https://github.com/conll/reference-coreference-scorers")
	sys.exit()

print("\t".join(["f","muc","bcub","ceafe","size","type"]))

if options.docname is None:
	options.docname = df['doc_id'].iloc[0]

target_idx = df.index[df['doc_id'].isin([options.docname])]

data = df.loc[target_idx].copy()

tokens, marks, group_freqs, opening_marks, closing_marks, single_marks, doc_start = read_gold(gold, options.docname)

cmd = [scorer, "all", options.goldfile, "tempfilename", options.docname]

for i, row in data.iterrows():

	bin_resp = row["bin_resp"]
	ana_miss = row["ana_miss"]
	ante_miss = row["ante_miss"]
	ana_id = row["cohort_id"].split(";")[1]
	d_tok = row["d_tok"]
	t_len = row["t_length"]

	ana_start, ana_end = ana_id.split("-")
	ana_start = str(int(ana_start) - 1)
	ana_end = str(int(ana_end) - 1)
	ana_id = ana_start + "-" + ana_end
	ante_end = str(int(ana_start) - d_tok)
	ante_start = str(int(ante_end) - t_len + 1)
	ante_id = ante_start + "-" + ante_end

	if bin_resp == 1:  # Getting this wrong means choosing NO coref
		ana_group = marks[ana_id]
		ante_group = marks[ante_id]
		new_group = "473692019374"
		size = str(group_freqs[ante_group]) + "\tfalse_neg"
		outcome = set_group(tokens, ana_id, new_group, opening_marks, closing_marks, single_marks, ana_group=ana_group)
	else:
		if ante_miss == 1:
			if ana_miss == 1: # Need to add an anaphor AND an antecedent = invent, False Anaphor error
				size = "0\tinvent_both"
				group = "473692019374"  # Invented group ID
			else: # Need to add ana to this non-existent antecedent
				size = "0\tinvent_ante"
				group = marks[ana_id]
			outcome = set_group(tokens, ana_id, group, opening_marks, closing_marks, single_marks,ante_id=ante_id)
		else:  # Wrong Link error
			group = marks[ante_id]
			if ana_miss == 1:
				size = str(group_freqs[group]) + "\tinvent_ana"
			else:
				size = str(group_freqs[group]) + "\twrong_link"
			outcome = set_group(tokens, ana_id, group, opening_marks, closing_marks, single_marks)

	outcome = doc_start + "\n" + outcome + "# end document\n"
	if options.remove_singletons:
		outcome = rem_singletons(outcome)
	report = exec_via_temp(outcome,cmd)
	scores = parse_report(report)
	score_str = "\t".join(list([str(100-x) for x in scores]))
	print(score_str + "\t" + size)
