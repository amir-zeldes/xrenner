#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
xrenner - eXternally configurable REference and Non-Named Entity Recognizer
xrenner.py
Main controller script for entity recognition and coreference resolution
Author: Amir Zeldes
"""

import argparse, sys
from modules.xrenner_xrenner import Xrenner
from glob import glob
from multiprocessing import Process, Value, Lock
from math import ceil


__version__ = "1.4.1"
xrenner_version = "xrenner V" + __version__

sys.dont_write_bytecode = True


class Counter(object):
	def __init__(self, initval=0):
		self.docs = Value('i', initval)
		self.sents = Value('i', initval)
		self.toks = Value('i', initval)
		self.lock = Lock()

	def increment(self,docs,sents,toks):
		with self.lock:
			self.docs.value += docs
			self.sents.value += sents
			self.toks.value += toks

	def value(self):
		with self.lock:
			return (self.docs.value,self.sents.value,self.toks.value)

def xrenner_worker(data,options,total_docs,counter):
	tokens = 0
	sentences = 0

	model = options.model
	override = options.override
	xrenner = Xrenner(model, override)

	for file_ in data:

		output = xrenner.analyze(file_, options.format)
		tokens += len(xrenner.conll_tokens)-1
		sentences += xrenner.sent_num-1

		if options.format == "none":
			pass
		elif options.format != "paula":
			if len(data) > 1:
				if options.format == "webanno":
					extension = "xmi"
				else:
					extension = options.format
				outfile = xrenner.docname + "." + extension
				handle = open(outfile, 'w')
				handle.write(output)
				handle.close()
			else:
				print output

		counter.increment(1,xrenner.sent_num-1,len(xrenner.conll_tokens)-1)
		docs, sents, toks = counter.value()

		if options.verbose and len(data) > 1:
			sys.stderr.write("Document " + str(docs) + "/" + str(total_docs) + ": " +
								 "Processed " + str(len(xrenner.conll_tokens)-1) + " tokens in " + str(xrenner.sent_num-1) + " sentences.\n")

if __name__ == "__main__":

	parser = argparse.ArgumentParser()
	parser.add_argument('-o', '--output', action="store", dest="format", default="sgml", help="output format, default: sgml; alternatives: html, paula, webanno, conll, onto, unittest, none")
	parser.add_argument('-m', '--model', action="store", dest="model", default="eng", help="input model directory name, in models/")
	parser.add_argument('-x', '--override', action="store", dest="override", default=None, help="specify a section in the model's override.ini file with alternative settings")
	parser.add_argument('-v', '--verbose', action="store_true", help="output run time and summary")
	parser.add_argument('-t', '--test', action="store_true", dest="test", help="run unit tests and quit")
	parser.add_argument('-p', '--procs', type=int, choices=xrange(1,17), dest="procs", help="number of processes for multithreading", default=2)
	parser.add_argument('file', action="store", help="input file name to process")
	parser.add_argument('--version', action='version', version=xrenner_version, help="show xrenner version number and quit")

	total_docs = 0
	counter = Counter(0)

	# Check if -t is invoked and run unit tests instead of parsing command line
	if len(sys.argv) > 1 and sys.argv[1] in ["-t", "--test"]:
		import unittest
		import modules.xrenner_test
		suite = unittest.TestLoader().loadTestsFromModule(modules.xrenner_test)
		unittest.TextTestRunner().run(suite)
	# Not a test run, parse command line as usual
	else:
		options = parser.parse_args()
		procs = options.procs
		if options.verbose:
			import modules.timing
			sys.stderr.write("\nReading language model...\n")

		data = glob(options.file)
		if not isinstance(data, list):
			split_data = [data]
		else:
			if len(data) < procs:  # Do not use more processes than files to process
				procs = len(data)
			chunk_size = int(ceil(len(data)/float(procs)))
			split_data = [data[i:i + chunk_size] for i in xrange(0, len(data), chunk_size)]

		jobs = []
		for sublist in split_data:
			p = Process(target=xrenner_worker,args=(sublist,options,len(data),counter))
			jobs.append(p)
			p.start()

		for j in jobs:
			j.join()

		total_docs, total_sentences, total_tokens = counter.value()

		if options.verbose:
			sys.stderr.write("="*40 + "\n")
			sys.stderr.write("Processed " + str(total_tokens) + " tokens in " + str(total_sentences) + " sentences.\n")
