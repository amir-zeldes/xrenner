#!/usr/bin/python
# -*- coding: utf-8 -*-


from argparse import ArgumentParser
import csv,re,sys,io,os
from random import choice, seed
from collections import defaultdict

seed(42)  # Reproducible random choice if thinning output to positive/negative match pairs
counter = 0

utils_dir = os.path.dirname(os.path.realpath(__file__))
DEV_DOCS = io.open(utils_dir + os.sep + "dev_docs.tab",encoding="utf8").read().strip().replace("\r","").split("\n")

parser = ArgumentParser()
parser.add_argument('gold_file', action="store", help="gold file name to process")
parser.add_argument('response_file', action="store", help="xrenner dump file name to process")
parser.add_argument('-b','--binary', action="store_true", help="output binary response only")
parser.add_argument('-d','--del_id', action="store_true", help="delete document position id")
parser.add_argument('-a','--appositions', action="store_true", help="leave appositions as is (otherwise, apposition envelopes are auto-fixed)")
parser.add_argument('-c','--copulas', action="store_true", help="leave copula predicates as is (otherwise they are auto-fixed)")
parser.add_argument('-p','--pairs', action="store_true", help="output single negative match for any cohort with a positive match")
parser.add_argument('-s','--single_negative', action="store_true", default="", help="output a single negative example for each cohort with no positive match")

options = parser.parse_args()

export_pairs = options.pairs
single_negative = options.single_negative

docname = ""
open_marks = {}
marks_by_end = {}  # Needed for tracking apposition envelopes
marks_by_start = {}
marks = {}
is_first = {}
gold_file = options.gold_file
last_cohort = ""
cohort_positive = False
cohort_cache = []

if sys.version_info[0] < 3:
	gold_handle = open(gold_file, 'rb')
else:
	gold_handle = open(gold_file, 'r', encoding='utf8')

with gold_handle as csvfile:
	reader = csv.reader(csvfile, delimiter='\t', escapechar="\\", quoting=csv.QUOTE_NONE)
	for fields in reader:
		if len(fields) > 0:
			if fields[0].startswith("# begin"):
				m = re.search("# begin document ([^\s]+)",fields[0])
				docname = m.group(1)
				seen_corefs = set([])
				is_first[docname] = {}
				open_marks[docname] = {}
				marks[docname] = {}
				marks_by_start[docname] = defaultdict(list)
				marks_by_end[docname] = defaultdict(list)
			elif len(fields) > 2:
				coref = fields[-1]
				if fields[0] == "66":
					pass
				fields[0] = str(int(fields[0])+1)
				if coref != "_":
					open_matches = re.findall(r'\(([0-9]+)',coref)
					for match in open_matches:
						open_marks[docname][match] = fields[0]
					close_matches = re.findall(r'([0-9]+)\)',coref)
					for match in close_matches:
						if match not in open_marks[docname]:
							sys.stderr.write("Unopened mark closed: doc " + docname + " tok " + fields[0]+ "\n")
							sys.exit()
						marks[docname][open_marks[docname][match]+"-"+fields[0]] = match
						marks_by_end[docname][fields[0]].append((match,open_marks[docname][match],fields[0]))
						marks_by_start[docname][open_marks[docname][match]].append((match,open_marks[docname][match],fields[0]))
						if match not in seen_corefs:
							is_first[docname][open_marks[docname][match]+"-"+fields[0]] = "1"
							seen_corefs.add(match)
						else:
							is_first[docname][open_marks[docname][match]+"-"+fields[0]] = "0"

t_func_col = ""
d_parent_col = ""
n_negated_col = ""

if sys.version_info[0] < 3:
	response_handle = open(options.response_file, 'rb')
else:
	import codecs
	sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
	response_handle = open(options.response_file, 'r', encoding='utf8')

with response_handle as csvfile:
	reader = csv.reader(csvfile, delimiter='\t', quoting=csv.QUOTE_NONE)

	first = True
	for i, row in enumerate(reader):
		if first:
			first = False
			headers = row[:]
			t_func_col = headers.index("t_func")
			n_negated_col = headers.index("n_negated")
			d_parent_col = headers.index("d_parent")
			if not options.binary:
				headers.append("ana_miss")
				headers.append("ante_miss")
				headers.append("n_first_mention")
			headers = headers[2:] + ["bin_resp"]
			if not options.del_id:
				headers = ["doc_id","cohort_id"] + headers
			print("\t".join(headers))
			continue
		fields = row[:]
		line = "\t".join(fields)
		if ";" in fields[0]:
			if fields[0] == "67-67;7-10":
				pass
			docname = fields[1]
			ana_group = ""
			ante_groups = []
			ana,ante=fields[0].split(";")
			responses = []
			t_func = fields[t_func_col]
			n_negated = fields[n_negated_col]
			d_parent = fields[d_parent_col]
			# Handle heuristic copula markable restoration (can be useful for corpora like OntoNotes, where predicates are not markables)
			if not options.copulas:
				if t_func == "nsubj" and d_parent == "1" and n_negated == "0":
					if ana not in marks[docname] and ante in marks[docname]:
						ana_start, ana_end = ana.split("-")
						ante_group = marks[docname][ante]
						marks[docname][ana] = ante_group
			if ana in marks[docname]:
				ana_group = marks[docname][ana]
			else:
				responses.append("ana_miss")
			if ante in marks[docname]:
				ante_group = marks[docname][ante]
				ante_groups.append(ante_group)
				# Handle OntoNotes style apposition envelopes if desired (i.e. [[Jane]_i,[a lawyer]_i]_j == [Jane]_j, [a lawyer]_j
				if "appos" in t_func and not options.appositions:
					ante_start, ante_end = ante.split("-")
					for group_id, start, end in marks_by_end[docname][ante_end]:
						if ante_group in [x[0] for x in marks_by_start[docname][start]] and ante_group != group_id:
							# This is a distinct markable, which has a mark with ante's grp# both at start and finish -> appos envelope
							ante_groups.append(group_id)
			if len(ante_groups) == 0:
				responses.append("ante_miss")
			if ana_group != "" and len(ante_groups) > 0:
				if ana_group in ante_groups:
					responses.append("match")
				else:
					responses.append("mismatch")

			response_string = ";".join(responses)
			out_fields = fields[2:]
			if not options.del_id:
				out_fields = [docname, docname + ";" + fields[0].split(";")[0]] + out_fields
			if not options.binary:
				ana_miss = str(int("ana_miss" in response_string))
				ante_miss = str(int("ante_miss" in response_string))
				out_fields.append(ana_miss)
				out_fields.append(ante_miss)
				ana_id = fields[0].split(";")[0]
				if ana_id in is_first[docname]:
					out_fields.append(is_first[docname][ana_id])
				else:
					out_fields.append("0")
			bin_resp = "0" if "match" not in responses else "1"
			out_fields.append(bin_resp)

			if docname in DEV_DOCS:
				print("\t".join(out_fields))
				counter += 1
			elif not export_pairs:
				print("\t".join(out_fields))
				counter += 1
			else:
				if last_cohort != docname + ana:  # new cohort
					if not cohort_positive:  # No matches, output all negative entries
						if len(cohort_cache) > 0:
							if single_negative:
								chosen = choice(cohort_cache)
								print(chosen)
								counter += 1
							else:
								print("\n".join(cohort_cache))
								counter += len(cohort_cache)
					else:  # There was a match, select a random negative paired example
						if len(cohort_cache) > 0:
							if export_pairs:
								chosen = choice(cohort_cache)
								print(chosen)
								counter += 1
							else:
								print("\n".join(cohort_cache))
								counter += len(cohort_cache)
					cohort_cache = []
					cohort_positive = False
					last_cohort = docname + ana
				else:
					if bin_resp == "1":  # Always output positive match
						cohort_positive = True
						print("\t".join(out_fields))
						counter += 1
					else:
						cohort_cache.append("\t".join(out_fields))

# Flush last cohort
if not cohort_positive or docname in DEV_DOCS:  # No matches, output all negative entries
	if len(cohort_cache) > 0:
		if single_negative:
			chosen = choice(cohort_cache)
			print(chosen)
			counter +=1
		else:
			print("\n".join(cohort_cache))
			counter += len(cohort_cache)
else:  # There was a match, select a random negative paired example
	if len(cohort_cache) > 0:
		if export_pairs:
			chosen = choice(cohort_cache)
			print(chosen)
			counter +=1
		else:
			print("\n".join(cohort_cache))
			counter += len(cohort_cache)

sys.stderr.write("Finished checking dump.\n\to Read:  " + str(i) + " lines of xrenner output\n\to Wrote: " + str(counter) + " checked responses")