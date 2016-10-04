=======
xrenner
=======

eXternally configurable REference and Non Named Entity Recognizer

https://corpling.uis.georgetown.edu/xrenner/


Usage::

   xrenner.py [options] INFILE (> OUTFILE)

Options:

-m, --model            input model directory name, in models/, default 'eng'
-o, --output           output format, default: sgml; alternatives: html, paula, webanno, conll, onto, unittest
-x, --override         specify a section in the model's override.ini file with alternative settings, default=None; possible values such as 'OntoNotes', 'GUM' 
-v, --verbose          output run time and summary
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
		6	2013	2013	CD	CD	_	3	tmod	_	_

Examples:
---------
* python xrenner.py example_in.conll10 > example_out.sgml
* python xrenner.py -x GUM example_in.conll10 > example_out.sgml
* python xrenner.py -o conll example_in.conll10 > example_out.conll
* python xrenner.py -m eng -o conll example_in.conll10 > example_out.conll
