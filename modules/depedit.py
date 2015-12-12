#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
DepEdit - A simple configurable tool for manipulating dependency trees
Input: CoNLL10 (10 columns, tab-delimited, blank line between sentences)
Author: Amir Zeldes
"""

import argparse
import re
import copy
import sys
from collections import defaultdict

__version__ = "1.1.0"


class ParsedToken:
	def __init__(self, tok_id, text, lemma, pos, morph, head, func, child_funcs):
		self.id = tok_id
		self.text = text
		self.pos = pos
		self.lemma = lemma
		self.morph = morph
		self.head = head
		self.func = func
		self.child_funcs = child_funcs


class Transformation:

	def parse_transformation(self, transformation_text):
		if transformation_text.count("\t") < 2:
			return None
		else:
			split_trans = transformation_text.split("\t")
			definition_string = split_trans[0]
			relation_string = split_trans[1]
			action_string = split_trans[2]
			relation_string = self.normalize_shorthand(relation_string)
			action_string = self.normalize_shorthand(action_string)
			definitions = definition_string.split(";")
			relations = relation_string.split(";")
			actions = action_string.split(";")
			return [definitions, relations,actions]

	@staticmethod
	def normalize_shorthand(criterion_string):
		temp = ""
		while temp != criterion_string:
			temp = criterion_string
			criterion_string = re.sub(r'(#[0-9]+)(>|\.(?:[0-9]+(?:,[0-9]+)?)?)(#[0-9]+)(>|\.(?:[0-9]+(?:,[0-9]+)?)?)', r'\1\2\3;\3\4', criterion_string)
		return criterion_string

	def __init__(self, transformation_text, line):
		instructions = self.parse_transformation(transformation_text)
		if instructions is None:
			message = "Depedit says: error in configuration file\n"
			message += "Malformed instruction on line " + str(line) + " (instruction lines must contain exactly two tabs)\n"
			sys.stderr.write(message)
			sys.exit()
		self.definitions = instructions[0]
		self.relations = instructions[1]
		self.actions = instructions[2]
		self.line = line

	def validate(self):
		report = ""
		for definition in self.definitions:
			nodes = definition.split(";")
			for node in nodes:
				criteria = node.split("&")
				for criterion in criteria:
					if not re.match("(text|pos|lemma|morph|func|head)=/[^/=]*/",criterion):
						report+= "Invalid node definition in column 1: " + criterion
		for relation in self.relations:
			if relation == "none" and len(self.relations) == 1:
				if len(self.definitions) > 1:
					report += "Column 2 setting 'none' invalid with more than one definition in column 1"
			elif relation == "none":
				report += "Setting 'none' invalid in column 2 when multiple relations are defined"
			else:
				criteria = relation.split(";")
				for criterion in criteria:
					criterion = criterion.strip()
					if not re.match(r"#[0-9]+((>|\.([0-9]+(,[0-9]+)?)?)#[0-9]+)+",criterion):
						report += "Column 2 relation setting invalid criterion: " + criterion + ". "
		for action in self.actions:
			commands = action.split(";")
			for command in commands:
				if not re.match("(#[0-9]+>#[0-9]+|#[0-9]+:(func|lemma|text|pos|morph|head)=[^=]*)$",command):
					report += "Column 3 invalid action definition: " + command + " and the action was " + action
		return report


def process_sentence(conll_tokens, tokoffset, transformations):
	for transformation in transformations:
		node_matches = defaultdict(list)
		for def_index, def_text in enumerate(transformation.definitions):
			for token in conll_tokens[tokoffset+1:]:
				if matches_definition(token,def_text):
					node_matches[def_index+1].append(token)
		result_sets = []
		for relation in transformation.relations:
			found = matches_relation(node_matches, relation, result_sets)
			if not found:
				result_sets = []
		result_sets = merge_sets(result_sets,len(transformation.definitions))
		if len(result_sets) > 0:
			for action in transformation.actions:
				execute_action(result_sets, action)
	return serialize_output_tree(conll_tokens[tokoffset + 1:], tokoffset)


def matches_definition(token,def_text):
	defs = def_text.split("&")
	for def_item in defs:
		criterion = def_item.split("=")[0]
		def_value = "^(" + def_item.split("=")[1][1:-1] + ")$"
		tok_value = getattr(token,criterion)
		if not re.match(def_value,tok_value):
			return False
	return True


def matches_relation(node_matches, relation, result_sets):
	if len(relation) == 0:
		return

	elif "." in relation:
		if re.match(r'.*\.[0-9]', relation):
			m = re.match(r'.*\.[0-9]*,?[0-9]*#', relation)
			operator = m.group()
			operator = operator[operator.find("."):operator.rfind("#")]
		else:
			operator = "."
	elif ">" in relation:
		operator = ">"

	matches = defaultdict(list)

	hits=0
	if relation == "none": # Unary operation on one node
		node1 = 1
		for tok1 in node_matches[node1]:
			hits += 1
			result = {}
			matches[node1].append(tok1)
			result[node1] = tok1
			result_sets.append(result)
	else:
		node1 = relation.split(operator)[0]
		node2 = relation.split(operator)[1]

		node1=int(node1.replace("#", ""))
		node2=int(node2.replace("#", ""))
		for tok1 in node_matches[node1]:
			for tok2 in node_matches[node2]:
				if test_relation(tok1, tok2, operator):
					result_sets.append({node1: tok1, node2: tok2})
					matches[node1].append(tok1)
					matches[node2].append(tok2)
					hits += 1

		for option in [node1,node2]:
			tokens_to_remove = []
			for token in node_matches[option]:
				if token not in matches[option]:
					tokens_to_remove.append(token)
			for token in tokens_to_remove:
				node_matches[option].remove(token)

	if hits == 0:  # No solutions found for this relation
		return False
	else:
		return True

def test_relation(node1,node2,operator):
	if operator == ".":
		if int(node2.id) == int(node1.id)+1:
			return True
		else:
			return False
	elif operator == ">":
		if int(node2.head) == int(node1.id):
			return True
		else:
			return False
	elif "." in operator:
		m = re.match(r'\.([0-9]+)(,[0-9]+)?',operator)
		if len(m.groups()) > 1:
			min_dist = int(m.group(1))
			if not m.group(2) is None:
				max_dist = int(m.group(2).replace(",",""))
			else:
				max_dist = min_dist
			if max_dist >= int(node2.id) - int(node1.id) >= min_dist:
				return True
			else:
				return False
		else:
			dist = int(m.group(1))
			if int(node2.id) - int(node1.id) == dist:
				return True
			else:
				return False


def merge_sets(sets,node_count):

	solutions = []
	bins = []
	for set_to_merge in sets:
		new_set = {}
		for key in set_to_merge:
			new_set[key] = set_to_merge[key]

		for bin in copy.copy(bins):
			if bins_compatible(new_set,bin):
				candidate = merge_bins(new_set,bin)
				bins.append(candidate)
		bins.append(new_set)

	for bin in bins:
		if len(bin) == node_count:
			solutions.append(bin)

	return solutions


def bins_compatible(bin1, bin2):
	overlap = False
	non_overlap = False
	for key in bin1:
		if key in bin2:
			if bin1[key] == bin2[key]:
				overlap = True
		if key not in bin2:
			non_overlap = True
	if overlap and non_overlap:
		return True
	else:
		return False

def merge_bins(bin1, bin2):
	for key in bin1:
		if key not in bin2:
			bin2[key]= bin1[key]
			return bin2


def execute_action(result_sets, action_list):
	actions = action_list.split(";")
	for result in result_sets:
		if len(result) > 0:
			for action in actions:
				if ":" in action:  # Unary node instruction
					node_position = int(action[1:action.find(":")])
					property = action[action.find(":")+1:action.find("=")]
					value = action[action.find("=")+1:].strip()
					setattr(result[node_position],property,value)
				else:  # Binary instruction
					if ">" in action:  # Head relation
						operator = ">"
						node1 = int(action.split(operator)[0].replace("#", ""))
						node2 = int(action.split(operator)[1].replace("#", ""))
						tok1 = result[node1]
						tok2 = result[node2]
						tok2.head = tok1.id


def serialize_output_tree(tokens, tokoffset):
	output_tree = ""
	for tok in tokens:
		output_tree += str(int(tok.id)-tokoffset)+"\t"+tok.text+"\t"+tok.lemma+"\t"+tok.pos+"\t"+tok.pos+"\t"+tok.morph+\
						"\t"+str(int(tok.head)-tokoffset)+"\t"+tok.func+"\t_\t_\n"
	output_tree += "\n"
	return output_tree


def run_depedit(infile, config_file):
	children = defaultdict(list)
	descendents = {}
	child_funcs = defaultdict(list)
	conll_tokens = []
	tokoffset = 0
	sentlength = 0

	transformations = []
	line_num = 0
	for instruction in config_file:
		line_num += 1
		if len(instruction)>0 and not instruction.startswith(";") and not instruction.startswith("#") and not instruction.strip() =="":
			transformations.append(Transformation(instruction, line_num))

	report = ""
	for transformation in transformations:
		trans_report = transformation.validate()
		if trans_report != "":
			report += "On line " + str(transformation.line) + ": " + trans_report +"\n"
	if len(report) > 0:
		report = "Depedit says: error in configuration file\n" + report
		sys.stderr.write(report)
		sys.exit()

	conll_tokens.append(0)
	my_output = ""

	for myline in infile:
		if myline.find("\t") > 0:  # Only process lines that contain tabs (i.e. conll tokens)
			cols = myline.split("\t")
			conll_tokens.append(ParsedToken(str(int(cols[0]) + tokoffset),cols[1],cols[2],cols[3],cols[5],str(int(cols[6]) + tokoffset),cols[7].strip(),[]))
			sentlength += 1
			children[str(int(cols[6]) + tokoffset)].append(str(int(cols[0]) + tokoffset))
			child_funcs[(int(cols[6]) + tokoffset)].append(cols[7])
		elif sentlength > 0:
			# TODO: Add list of all funcs dependent on this token to its child_funcs as a possible further condition
			#for id in child_funcs:
			#	for func in child_funcs[id]:
			#		if not func in conll_tokens[id].child_funcs:
			#			conll_tokens[id].child_funcs.append(func)
			my_output += process_sentence(conll_tokens,tokoffset,transformations)
			if sentlength > 0:
				tokoffset += sentlength

			sentlength = 0

	if sentlength > 0:  # Leftover sentence did not have trailing newline
		my_output += process_sentence(conll_tokens,tokoffset,transformations)

	return my_output

if __name__ == "__main__":
	depedit_version = "DepEdit V" + __version__
	parser = argparse.ArgumentParser()
	parser.add_argument('-c', '--config', action="store", dest="config", default="config.ini", help="Configuration file defining transformation")
	parser.add_argument('--version', action='version', version=depedit_version)
	parser.add_argument('file',action="store",help="Input file name to process")
	options = parser.parse_args()

	infile = open(options.file)
	config_file = open(options.config)
	output_trees = run_depedit(infile, config_file)
	print output_trees
