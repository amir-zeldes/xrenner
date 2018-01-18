#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
import io
import glob
from collections import defaultdict

class ParsedToken:
	def __init__(self, tok_id, text, lemma, pos, head, func):
		self.id = tok_id
		self.text = text
		self.pos = pos
		self.head = head
		self.func = func
		self.type = "UNKNOWN"
		self.lemma = lemma

parser = argparse.ArgumentParser()
parser.add_argument('-e','--entities',action="store",default="entity_heads.tab",help="Input file name of entity head list, i.e. model's entity_heads.tab")
parser.add_argument('-r','--results', action="store",default="entity_deps.tab",help="Input file name to write positive results to")
parser.add_argument('-u','--unknown', action="store",default="dep_unknown.tab",help="Input file name to write unknown type results to")
parser.add_argument('-a','--ambig',   action="store",default="dep_ambig.tab",help="Input file name to write ambiguous type results to")
parser.add_argument('-d','--dep_files', action="store",default="*.conllu",help="Path with glob pattern for dependency files to read")

options = parser.parse_args()

entities = io.open(options.entities, encoding="utf8")
results  = io.open(options.results, 'w', encoding="utf8")
unknown  = io.open(options.unknown, 'w', encoding="utf8")
ambig	 = io.open(options.ambig, 'w', encoding="utf8")


# Build entity dictionary out of file
entdict = {}
for myline in entities:
	if myline.find("\t") > 0:
		splitline = myline.split("\t")
		text = splitline[0]
		type = splitline[1]

		if text in entdict.keys():
			# Check if new ent is diff, if so add
			if type not in entdict[text]:
				entdict[text] += [type]
		else:
			entdict[text] = [type]

seen_unknown = set([])
seen_ambig = set([])
entity_deps = defaultdict(int)

for filename in glob.glob(options.dep_files):  # Loops over conll file(s)

	myfile = io.open(filename, encoding="utf8")

	conll_tokens = []

	for myline in myfile:
		if myline.find("\t") > 0:  # Only process lines that contain tabs (i.e. conll tokens)
			cols = myline.split("\t")
			conll_tokens.append(ParsedToken(str(int(cols[0])),cols[1],cols[2],cols[4],str(int(cols[6])),cols[7].strip()))

	for i in range(0, len(conll_tokens)):
		tok = conll_tokens[i]

		if tok.pos.startswith('N') or tok.pos == 'PROPN': # matches nouns in various tagsets
			# find parent text
			if tok.head == '0':
				parenttext = "[ROOT]"
			else:
				offset = int(tok.head) - int(tok.id)
				parent = conll_tokens[i + offset]
				parenttext = parent.text

			# Try to find entity type
			if tok.text in entdict.keys():
				if len(entdict[tok.text]) == 1:
					tok.type = entdict[tok.text][0]
				else:
					tok.type = "AMBIG"
			else:
				#tok.lemma = lemmatize(tok.text)  # Insert custom lemmatizer here if desired
				if tok.lemma in entdict.keys():
					if len(entdict[tok.lemma]) == 1:
						tok.type = entdict[tok.lemma][0]
					else:
						tok.type = "AMBIG"

			# Write result to appropriate file
			if tok.type == "UNKNOWN":
				if tok.text not in seen_unknown:
					unknown.write(tok.text + '\n')
					seen_unknown.add(tok.text)
			elif tok.type == "AMBIG":
				if tok.text not in seen_ambig:
					if tok.text in entdict: # ambig based on original token
						ambig.write(parenttext + '\t' + tok.func + '\t' + str(entdict[tok.text]) + '\n')
					elif tok.lemma in entdict: # ambig based on lemma
						ambig.write(parenttext + '\t' + tok.func + '\t' + str(entdict[tok.lemma]) + '\n')
					seen_ambig.add(tok.text)

			if tok.type != "UNKNOWN":
				if tok.text in entdict or tok.lemma in entdict:
					entity_deps[parenttext + '\t' + tok.func + '\t' + tok.type] += 1


	myfile.close()

for k, v in [(k, entity_deps[k]) for k in sorted(entity_deps, key=entity_deps.get, reverse=True)]:
	results.write(k + "\t" + str(v) + "\n")


results.close()
unknown.close()
ambig.close()
