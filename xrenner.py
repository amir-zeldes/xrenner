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
parser.add_argument('-o', '--output', action="store", dest="format", default="sgml", help="Output format, default: sgml; alternatives: html, paula, webanno, conll")
parser.add_argument('-m', '--model', action="store", dest="model", default="eng", help="Input model directory name, in models/")
parser.add_argument('-x', '--override', action="store", dest="override", default=None, help="Provide an override file to run alternative settings for config.ini")
parser.add_argument('-v', '--verbose', action="store_true", help="Output run time and summary")
parser.add_argument('file', action="store", help="Input file name to process")
parser.add_argument('--version', action='version', version=xrenner_version)

options = parser.parse_args()
if options.verbose:
	import modules.timing

model = options.model
override = options.override

xrenner = Xrenner(model, override)
output = xrenner.analyze(options)

if options.format != "paula":
	print output


if options.verbose:
	sys.stderr.write("="*40 + "\n")
	sys.stderr.write("Processed " + str(len(xrenner.conll_tokens)-1) + " tokens in " + str(xrenner.sent_num-1) + " sentences.\n")
