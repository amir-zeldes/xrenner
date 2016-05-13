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

__version__ = "1.2.x"  # Develop
xrenner_version = "xrenner V" + __version__

sys.dont_write_bytecode = True

parser = argparse.ArgumentParser()
parser.add_argument('-o', '--output', action="store", dest="format", default="sgml", help="output format, default: sgml; alternatives: html, paula, webanno, conll, onto, unittest")
parser.add_argument('-m', '--model', action="store", dest="model", default="eng", help="input model directory name, in models/")
parser.add_argument('-x', '--override', action="store", dest="override", default=None, help="specify a section in the model's override.ini file with alternative settings")
parser.add_argument('-v', '--verbose', action="store_true", help="output run time and summary")
parser.add_argument('file', action="store", help="input file name to process")
parser.add_argument('-t', '--test', action="store_true", dest="test", help="run unit tests and quit")
parser.add_argument('--version', action='version', version=xrenner_version, help="show xrenner version number and quit")


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

	model = options.model
	override = options.override
	parse = open(options.file)
	xrenner = Xrenner(model, override)
	output = xrenner.analyze(parse, options.format)

	if options.format != "paula":
		print output

	if options.verbose:
		sys.stderr.write("="*40 + "\n")
		sys.stderr.write("Processed " + str(len(xrenner.conll_tokens)-1) + " tokens in " + str(xrenner.sent_num-1) + " sentences.\n")
