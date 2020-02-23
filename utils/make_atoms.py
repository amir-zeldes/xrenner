import io, re, os, sys
from glob import glob
from argparse import ArgumentParser
from collections import defaultdict

p = ArgumentParser()
p.add_argument("files",help="WebAnno TSV files, e.g. *.tsv")

opts = p.parse_args()

tsv_files = glob(opts.files)

non_atoms = defaultdict(int)
atoms = defaultdict(int)

for file_ in tsv_files:
	toks2ents = defaultdict(set)
	ents2text = defaultdict(str)
	ents2toks = defaultdict(set)
	lines = io.open(file_, encoding="utf8").readlines()
	toknum = 0
	for line in lines:
		if "\t" in line:
			toknum += 1
			fields = line.split()
			token = fields[2]
			ents = fields[3]
			if ents == "_":
				continue
			for ent in ents.split("|"):
				toks2ents[toknum].add(ent)
				ents2text[ent] += token + " "
				ents2toks[ent].add(toknum)

	# Make spans
	spans = {}
	starts = defaultdict(set)
	for ent in ents2toks:
		spans[ent] = (min(ents2toks[ent]),max(ents2toks[ent]))
		starts[min(ents2toks[ent])].add(ent)

	# For each ent check if another starts in its span
	for ent in spans:
		start, end = spans[ent]
		starting_spans = 0
		for i in range(start, end+1):
			if i in starts:
				starting_spans+=len(starts[i])
		if starting_spans == 1 and start != end:  # Multi-token atom
			atoms[ents2text[ent]] += 1
			if ents2text[ent] == "your phone ":
				print(file_)
		elif start != end:
			non_atoms[ents2text[ent]] += 1

ambig = set()

with io.open("atoms.tab",'w',encoding="utf8",newline="\n") as f:
	for atom in sorted(atoms, key=atoms.get, reverse=True):
		if atom in non_atoms:
			ambig.add(atom)
		else:
			f.write(atom.strip() + "\t" + str(atoms[atom]) + "\n")

with io.open("atoms_ambig.tab",'w',encoding="utf8",newline="\n") as f:
	for atom in sorted(ambig, key=atoms.get, reverse=True):
		f.write(atom.strip() + "\t" + str(atoms[atom]) + "\t" + str(non_atoms[atom]) + "\n")

