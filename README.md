xrenner - eXternally configurable REference and Non Named Entity Recognizer

Usage: 
========
xrenner.py [options] INFILE (> OUTFILE)

options:
  * -o, --output	Output format, default: sgml; alternatives: html, paula, webanno, conll
  * -m, --model	Input model directory name, in models/
  * -x, --override Override settings in the specified sections of config.ini by reading from override.ini, default=None; possible values such as 'OntoNotes', 'GUM' 
  * --version	Print xrenner version and quit

Examples:
========
  * python xrenner.py example_in.conll10 > example_out.sgml
  * python xrenner.py -x GUM example_in.conll10 > example_out.sgml
  * python xrenner.py -o conll example_in.conll10 > example_out.conll
  * python xrenner.py -m eng -o conll example_in.conll10 > example_out.conll
