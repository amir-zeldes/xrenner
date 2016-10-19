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


__version__ = "1.4.1" 
xrenner_version = "xrenner V" + __version__

sys.dont_write_bytecode = True

if __name__ == "__main__":

	parser = argparse.ArgumentParser()
	parser.add_argument('-o', '--output', action="store", dest="format", default="sgml", help="output format, default: sgml; alternatives: html, paula, webanno, conll, onto, unittest, none")
	parser.add_argument('-m', '--model', action="store", dest="model", default="eng", help="input model directory name, in models/")
	parser.add_argument('-x', '--override', action="store", dest="override", default=None, help="specify a section in the model's override.ini file with alternative settings")
	parser.add_argument('-v', '--verbose', action="store_true", help="output run time and summary")
	parser.add_argument('file', action="store", help="input file name to process")
	parser.add_argument('-t', '--test', action="store_true", dest="test", help="run unit tests and quit")
	parser.add_argument('--version', action='version', version=xrenner_version, help="show xrenner version number and quit")

	total_tokens = 0
	total_sentences = 0
	docnum = 0

	# Check if -t is invoked and run unit tests instead of parsing command line
	if len(sys.argv) > 1 and sys.argv[1] in ["-t", "--test"]:
		import unittest
		import modules.xrenner_test
		suite = unittest.TestLoader().loadTestsFromModule(modules.xrenner_test)
		unittest.TextTestRunner().run(suite)
	# Not a test run, parse command line as usual
	else:
		options = parser.parse_args()
		if options.verbose:
			import modules.timing
			sys.stderr.write("\nReading language model...\n") 

		model = options.model
		override = options.override
		xrenner = Xrenner(model, override)

		data = glob(options.file)
		if not isinstance(data,list):
			data = [data]
		for file_ in data:

			docnum += 1

			if options.verbose:
				if len(data) > 1:
					sys.stderr.write("Processing document " + str(docnum) + "/" + str(len(data)) + "... ") 
				else:
					sys.stderr.write("Processing document...\n")

			output = xrenner.analyze(file_, options.format)
			total_tokens += len(xrenner.conll_tokens)-1
			total_sentences += xrenner.sent_num-1
			
			if options.format == "none":
				pass
			elif options.format != "paula":
				if len(data) > 1:
					outfile = xrenner.docname + "." + options.format
					handle = open(outfile, 'w')
					handle.write(output)
					handle.close()
				else:
					print output

			if options.verbose and len(data) > 1:
				sys.stderr.write("Processed " + str(len(xrenner.conll_tokens)-1) + " tokens in " + str(xrenner.sent_num-1) + " sentences.\n")

		if options.verbose:
			sys.stderr.write("="*40 + "\n")
			sys.stderr.write("Processed " + str(total_tokens) + " tokens in " + str(total_sentences) + " sentences.\n")
