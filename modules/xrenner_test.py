"""
Module to generate and run unit tests

Author: Amir Zeldes
"""

from collections import defaultdict
import unittest
import re, os
from xrenner_xrenner import Xrenner

def generate_test(conll_tokens, markables, parse, model="eng", name="test"):
	tok_count = len(conll_tokens)
	mark_count = 0
	ids = []
	marks_by_id = {}

	# Collect markable groups, assign IDs by extension and count markables
	marks_by_group = defaultdict(list)
	for mark in markables:
		mark_count += 1

		# Assign predictable ID of the form start_end
		id_ = str(mark.start) + "_" + str(mark.end)
		if id_ in ids:
			raise("xrenner generated two markables with same extension: tok" + str(mark.start) + ":tok" + str(mark.end))
		else:
			ids.append(id_)
			mark.id = id_
			marks_by_id[id_] = mark

		marks_by_group[int(mark.group)].append(mark)

	group_count = len(marks_by_group)

	# Serialize group details
	chains = []
	for group in sorted(marks_by_group):
		chain = sorted(marks_by_group[group],key=lambda x: int(x.id[:x.id.find("_")]))
		gid = "g" + chain[0].id
		chain_string = "  "
		for mark in chain:
			chain_string += mark.id + " < "
		chains.append(chain_string[:-3])

	chains.sort(key=lambda x: int(x[2:x.find("_")]))

	snippets = []
	for chain in chains:
		first = chain[2:chain.find("<")-1]
		snippet = marks_by_id[first].text[:20] + "..." if len(marks_by_id[first].text) > 20 else marks_by_id[first].text
		snippets.append(snippet)

	zipped = zip(snippets,chains)

	output = ""
	output += "name:" + name + "\n"
	output += "model:" + model + "\n"
	output += "toks:" + str(tok_count) + " # " + " ".join(tok.text for tok in conll_tokens[1:4]) + "..." + "\n"
	output += "marks:" + str(mark_count) + "\n"
	output += "groups:" + str(group_count) + "\n"
	output += "chains:" + "\n"
	for chain in zipped:
		output += "  # " + str(chain[0]) + "\n"
		output += chain[1] + "\n"
	output += "input_data:" + "\n"
	output += "\n".join(parse)
	output += "\n" + "-"*5 + "\n"
	return output


class TestCorefMethods(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		# Read test/tests.dat
		print "\nxrenner unit tests\n" +"="*20 + "\nReading test cases from test/tests.dat"
		file = os.path.dirname(os.path.realpath(__file__)) + os.sep + ".." + os.sep + "test" + os.sep + "tests.dat"
		cls.test_data = ""
		with open(file, 'rb') as f:
			cls.test_data = f.read()

		# Populate cases with Case objects
		cls.cases = {}
		cases = cls.test_data.split("-----")
		for case in cases:
			case = case.strip()
			if len(case) > 0:
				case_to_add = Case(case)
				cls.cases[case_to_add.name] = case_to_add

		# Initialize an Xrenner object with the language model
		print "Initializing xrenner model 'eng'\n"
		cls.xrenner = Xrenner("eng")

	def test_cardinality(self):
		# I saw two birds . The three birds flew .
		print "\nRun cardinality test:  ",
		target = self.cases["cardinality_test"]
		result = Case(self.xrenner.analyze(target.parse.split("\n"),"unittest"))
		self.assertEqual(0,result.mark_count,"cardinality test (two birds != the three birds)")

	def test_appos_envelope(self):
		# Meet [[Mark Smith] , [the Governor]]. [He] is the best.
		print "\nRun apposition envelope test:  ",
		target = self.cases["appos_envelope"]
		result = Case(self.xrenner.analyze(target.parse.split("\n"),"unittest"))
		self.assertEqual(target.chains,result.chains,"appos envelope test")

	def test_isa(self):
		# I read [the Wallstreet Journal]. [That newspaper] is great.
		print "\nRun isa test:  ",
		target = self.cases["isa_test"]
		result = Case(self.xrenner.analyze(target.parse.split("\n"),"unittest"))
		self.assertEqual(target.chains,result.chains,"isa test (Wallstreet Journal <- newspaper)")

	def test_hasa(self):
		# The [[CEO] and the taxi driver] ate . [[His] employees] joined them
		print "\nRun hasa test:  ",
		target = self.cases["hasa_test"]
		result = Case(self.xrenner.analyze(target.parse.split("\n"),"unittest"))
		self.assertEqual(target.chains,result.chains,"hasa test (CEO, taxi driver <- his employees)")

	def test_dynamic_hasa(self):
		# Beth was worried about [[Sinead 's] well-being] , and also about Jane . [[Her] well-being] was always a concern .
		print "\nRun dynamic hasa test:  ",
		target = self.cases["dynamic_hasa_test"]
		result = Case(self.xrenner.analyze(target.parse.split("\n"),"unittest"))
		self.assertEqual(target.chains,result.chains,"dynamic hasa test (Sinead 's <- her)")

	def test_entity_dep(self):
		# I have a book , [a dog] and a car. [It] barked.
		print "\nRun entity dep test:  ",
		target = self.cases["entity_dep_test"]
		result = Case(self.xrenner.analyze(target.parse.split("\n"),"unittest"))
		self.assertEqual(target.chains,result.chains,"entity dep test (a book, a dog <- It barked)")

	def test_affix_morphology(self):
		# [A blorker] and an animal and a car . Of these , I saw [the person] .
		print "\nRun affix morphology test:  ",
		target = self.cases["morph_test"]
		result = Case(self.xrenner.analyze(target.parse.split("\n"),"unittest"))
		self.assertEqual(target.chains,result.chains,"affix morph test (a blorker <- the person)")

	def test_verbal_event_stem(self):
		# John [visited] Spain . [The visit] went well .
		print "\nRun verbal event coreference test:  ",
		target = self.cases["verb_test"]
		result = Case(self.xrenner.analyze(target.parse.split("\n"),"unittest"))
		self.assertEqual(target.chains,result.chains,"verbal event stemming (visited <- the visit	)")


class Case:

	def __init__(self, case_string):
		params, parse = case_string.split("input_data:")
		self.parse = parse.strip()
		params = params.replace("\r","")

		self.chains = []
		chain_mode = False

		for line in params.split("\n"):
			line = re.sub(r'#.*','',line).strip()
			if len(line) > 0:
				if chain_mode:
					self.chains.append(line)
				if ":" in line and not chain_mode and not "options" in line:
					key, val = line.split(":")
					if key == "name":
						self.name = val
					elif key == "toks":
						self.tok_count = int(val)
					elif key == "marks":
						self.mark_count = int(val)
					elif key == "groups":
						self.group_count = int(val)
					elif key == "model":
						self.model = val
					elif key == "chains":
						chain_mode = True

if __name__ == '__main__':
	unittest.main()