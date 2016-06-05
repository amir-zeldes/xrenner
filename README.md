xrenner - eXternally configurable REference and Non Named Entity Recognizer

https://corpling.uis.georgetown.edu/xrenner/

Usage: 
========
xrenner.py [options] INFILE (> OUTFILE)

options:
  * -m, --model	input model directory name, in models/, default 'eng'
  * -o, --output	output format, default: sgml; alternatives: html, paula, webanno, conll, onto, unittest
  * -x, --override specify a section in the model's override.ini file with alternative settings, default=None; possible values such as 'OntoNotes', 'GUM' 
  * -v, --verbose	output run time and summary
  * -t, --test	run unit tests and quit
  * --version	print xrenner version and quit

Examples:
========
  * python xrenner.py example_in.conll10 > example_out.sgml
  * python xrenner.py -x GUM example_in.conll10 > example_out.sgml
  * python xrenner.py -o conll example_in.conll10 > example_out.conll
  * python xrenner.py -m eng -o conll example_in.conll10 > example_out.conll
