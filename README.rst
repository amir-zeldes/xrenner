=======
xrenner
=======

eXternally configurable REference and Non Named Entity Recognizer

https://corpling.uis.georgetown.edu/xrenner/


Usage::

   xrenner.py [options] INFILE (> OUTFILE)
   xrenner.py [options] *.conllu

Options:

-m, --model            input model name in models/, default 'eng'
-o, --output           output format, default: sgml; alternatives: html, paula, webanno, webannotsv, conll, onto, unittest
-x, --override         specify a section model's override.ini file with alternative settings; e.g. OntoNotes or GUM for English
-v, --verbose          output run time and summary
-r, --rulebased        rule based operation, disable stochastic classifiers in selected model
-d, --dump <FILE>      dump all anaphor-antecedent candidate pairs to <FILE> to train classifiers
-p, --procs NUM        number of processes to run in parallel (only useful if running on multiple documents)
-t, --test             run unit tests and quit

--version              print xrenner version and quit

More exotic options:

--oracle               use external file with entity type predictions per token span (for integrating separate NER)
--noseq                do not use machine learning sequence tagger even when available


Input format:

	.. code-block:: html

		1	Wikinews	_	PROPN	NNP	_	2	nsubj	_	_
		2	interviews	_	VERB	VBZ	_	0	root	_	_
		3	President	_	NOUN	NN	_	2	obj	_	_
		4	of	_	ADP	IN	_	7	case	_	_
		5	the	_	DET	DT	_	7	det	_	_
		6	International	_	PROPN	NNP	_	7	amod	_	_
		7	Brotherhood	_	PROPN	NNP	_	3	nmod	_	_
		8	of	_	ADP	IN	_	9	case	_	_
		9	Magicians	_	PROPN	NNPS	_	7	nmod	_	_

		1	Wednesday	_	PROPN	NNP	_	0	root	_	_
		2	,	_	PUNCT	,	_	4	punct	_	_
		3	October	_	PROPN	NNP	_	4	compound	_	_
		4	9	_	NUM	CD	_	1	appos	_	_
		5	,	_	PUNCT	,	_	6	punct	_	_
		6	2013	_	NUM	CD	_	4	nmod:tmod	_	_


Format for external NER predictions when using --oracle option:

	.. code-block:: html

		Soaking the Bowl in Boiling Water
		2,4 object|5,7 substance
		2,4 object|5,7 substance

		Choose artwork with cool colors .
		2,6 object|4,6 abstract
		2,3 object|4,6 abstract

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

Note that by default, the English model is invoked (-m eng), and this model expects input in Universal Dependencies.

To use neural entity classification and machine learning coreference prediction with the English model, flair and xgboost must be installed (see requirements.txt)

Module usage:
-------------

.. code-block:: python

   from xrenner import Xrenner
   
   xrenner = Xrenner()
   # Get a parse in Universal Dependencies
   my_conllx_result = some_parser.parse("John visited Spain. His visit went well.")
   
   sgml_result = xrenner.analyze(my_conllx_result,"sgml")
   print(sgml_result)
   