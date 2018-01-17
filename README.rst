=======
xrenner
=======

eXternally configurable REference and Non Named Entity Recognizer

https://corpling.uis.georgetown.edu/xrenner/


Usage::

   xrenner.py [options] INFILE (> OUTFILE)
   xrenner.py [options] *.conllx

Options:

-m, --model            input model name in models/, default 'eng'
-o, --output           output format, default: sgml; alternatives: html, paula, webanno, conll, onto, unittest
-x, --override         specify a section model's override.ini file with alternative settings; e.g. OntoNotes or GUM for English
-v, --verbose          output run time and summary
-r, --rulebased        rule based operation, disable stochastic classifiers in selected model
-d, --dump <FILE>      dump all anaphor-antecedent candidate pairs to <FILE> to train classifiers
-p, --procs NUM        number of processes to run in parallel (only useful if running on multiple documents)
-t, --test             run unit tests and quit
--version              print xrenner version and quit


Input format:

	.. code-block:: html

		1	Wikinews	Wikinews	NP	NNP	_	2	nsubj	_	_
		2	interviews	interview	VVZ	VBZ	_	0	root	_	_
		3	President	president	NN	NN	_	2	dobj	_	_
		4	of	of	IN	IN	_	3	prep	_	_
		5	the	the	DT	DT	_	7	det	_	_
		6	International	international	NP	NNP	_	7	amod	_	_
		7	Brotherhood	brotherhood	NP	NNP	_	4	pobj	_	_
		8	of	of	IN	IN	_	7	prep	_	_
		9	Magicians	magician	NPS	NNPS	_	8	pobj	_	_
											
		1	Wednesday	Wednesday	NP	NNP	_	0	root	_	_
		2	,	,	,	,	_	0	punct	_	_
		3	October	October	NP	NNP	_	4	nn	_	_
		4	9	9	CD	CD	_	1	appos	_	_
		5	,	,	,	,	_	0	punct	_	_
		6	2013	2013	CD	CD	_	4	tmod	_	_

Installation:
-------------
Download the repo and use the main xrenner.py script on an input file, or install from PyPI and import as a module::

   > pip install xrenner


Examples:
---------
* python xrenner.py example_in.conll10 > example_out.sgml
* python xrenner.py -x GUM example_in.conll10 > example_out.sgml
* python xrenner.py -o conll example_in.conll10 > example_out.conll
* python xrenner.py -m eng -o conll *.conll10 (automatically names output files based on input files)

Note that by default, the English model is invoked (-m eng), and this model expects input in Basic Stanford Typed Dependencies (not Universal Dependencies).

Module usage:
-------------

.. code-block:: python

   from xrenner import Xrenner
   
   xrenner = Xrenner()
   # Get a parse in basic Stanford Dependencies (not UD)
   my_conllx_result = some_parser.parse("John visited Spain. His visit went well.")
   
   sgml_result = xrenner.analyze(my_conllx_result,"sgml")
   print(sgml_result)
   