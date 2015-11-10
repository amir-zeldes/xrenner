xrenner - eXternally configurable REference and Non Named Entity Recognizer

Usage: 
========
xrenner.py [options] INFILE (> OUTFILE)

options:
  * -o, --output	Output format, default: sgml; alternatives: html, paula, webanno, conll
  * -m, --model	Input model directory name, in models/
  * --version	Print xrenner version and quit

Examples:
========
  * Python xrenner.py example_in.conll10 > example_out.sgml
  * Python xrenner.py -o conll example_in.conll10 > example_out.conll
  * Python xrenner.py -m eng -o conll example_in.conll10 > example_out.conll