# encoding=utf8
import sys
import operator
import re
import os

reload(sys)
sys.setdefaultencoding('utf8')
"""
Output module for exporting resolved data to one of the supported serialization formats

Author: Amir Zeldes
"""


def clean_filename(filename):
	"""
	Heuristically replaces known extensions to create sensible output file name

	:param filename: the input file name to strip extensions from
	"""
	if filename.endswith(".conll10") or filename.endswith(".conllu") and not filename.startswith("."):
		return filename.replace(".conll10", "").replace(".conllu", "")


def output_onto(conll_tokens, markstart_dict, markend_dict, file_name):
	"""
	Outputs analysis results in OntoNotes .coref XML format
	
	:param conll_tokens: List of all processed ParsedToken objects in the document
	:param markstart_dict: Dictionary from markable starting token ids to Markable objects
	:param markend_dict: Dictionary from markable ending token ids to Markable objects
	:return: serialized XML
	"""

	output_string = '<DOC DOCNO="' + file_name + '">\n<TEXT PARTNO="000">\n'
	for out_tok in conll_tokens:
		if int(out_tok.id) in markstart_dict:
			for out_mark in sorted(markstart_dict[int(out_tok.id)], key=operator.attrgetter('end'), reverse=True):
				output_string += '<COREF ID="' + str(out_mark.group) + '" ENTITY="' + out_mark.entity + '" INFSTAT="' + out_mark.infstat
				if not out_mark.antecedent == "none":
					output_string += '" TYPE="' + out_mark.coref_type
				output_string += '">'
		if int(out_tok.id) > 0:
			output_string += re.sub("&","&amp;",out_tok.text) if ";" not in out_tok.text else out_tok.text
		if int(out_tok.id) in markend_dict:
			for out_mark in markend_dict[int(out_tok.id)]:
				output_string += "</COREF>"
		if int(out_tok.id) > 0:
			output_string += ' '


	return output_string + "\n</TEXT>\n</DOC>\n"


def output_SGML(conll_tokens, markstart_dict, markend_dict):
	"""
	Outputs analysis results as CWB SGML (with nesting), one token per line and markables in <referent> tags
	
	:param conll_tokens: List of all processed ParsedToken objects in the document
	:param markstart_dict: Dictionary from markable starting token ids to Markable objects
	:param markend_dict: Dictionary from markable ending token ids to Markable objects
	:return: serialized SGML
	"""

	output_string = ""
	for out_tok in conll_tokens:
		if int(out_tok.id) in markstart_dict:
			for out_mark in sorted(markstart_dict[int(out_tok.id)], key=operator.attrgetter('end'), reverse=True):
				output_string += '<referent id="' + str(out_mark.id) + '" entity="' + out_mark.entity + '" group="' + str(out_mark.group)
				if not out_mark.antecedent == "none":
					output_string += '" antecedent="' + str(out_mark.antecedent.id) + '" type="' + out_mark.coref_type
				output_string += '">\n'
		if int(out_tok.id) > 0:
			output_string += out_tok.text + "\n"
		if int(out_tok.id) in markend_dict:
			for out_mark in markend_dict[int(out_tok.id)]:
				output_string += "</referent>\n"

	return output_string


def output_conll(conll_tokens, markstart_dict, markend_dict, file_name, output_infstat=False):
	"""
	Outputs analysis results in CoNLL format, one token per line and markables with opening
	and closing numbered brackets. Compatible with CoNLL scorer.
	
	:param conll_tokens: List of all processed ParsedToken objects in the document
	:param markstart_dict: Dictionary from markable starting token ids to Markable objects
	:param markend_dict: Dictionary from markable ending token ids to Markable objects
	:param file_name: name of the source file (dependency data) to create header for CoNLL file
	:param output_infstat: whether to append the infstat property of each markable in a separate column (default False)
	:return: serialized conll format in plain text
	"""
	output_string = "# begin document " + str(file_name).replace(".conll10", "").replace("_xrenner","").replace("_hyph","").replace("_deped","").replace("_decyc","")+"\n"
	i = -1
	for out_tok in conll_tokens[1:]:
		i += 1
		coref_col = ""
		line = str(i) + "\t" + out_tok.text + "\t"
		infstat_col = ""
		if output_infstat:
			infstat_col = "_"
		if int(out_tok.id) in markstart_dict:
			for out_mark in sorted(markstart_dict[int(out_tok.id)], key=operator.attrgetter('end'), reverse=True):
				coref_col += "(" + str(out_mark.group)
				if output_infstat:
					infstat_col = out_mark.infstat
				if int(out_tok.id) in markend_dict:
					if out_mark in markend_dict[int(out_tok.id)]:
						coref_col += ")"
						markend_dict[int(out_tok.id)].remove(out_mark)
		if int(out_tok.id) in markend_dict:
			for out_mark in markend_dict[int(out_tok.id)]:
				if out_mark in markstart_dict[int(out_tok.id)]:
					coref_col += ")"
				else:
					if len(coref_col) > 0:
						if coref_col[-1].isdigit():
							coref_col += "|"  # Use pipe to separate group 1 opening and 2 closing leading to (12) -> (1|2)
					coref_col += str(out_mark.group) + ")"
		if int(out_tok.id) not in markstart_dict and int(out_tok.id) not in markend_dict:
			coref_col = "_"

		line += infstat_col + "\t" + coref_col
		output_string += line + "\n"
	output_string += "# end document\n\n"
	return output_string


def output_HTML(conll_tokens, markstart_dict, markend_dict, rtl=False):
	"""
	Outputs analysis results as HTML (assuming jquery, xrenner css and js files), one token per line and
	markables in <div> tags with Font Awesome icons and colored groups.
	
	:param conll_tokens: List of all processed ParsedToken objects in the document
	:param markstart_dict: Dictionary from markable starting token ids to Markable objects
	:param markend_dict: Dictionary from markable ending token ids to Markable objects
	:return: serialized HTML
	"""

	if rtl:
		rtl_style = ' style="direction: rtl"'
	else:
		rtl_style = ""

	output_string = '''<html>
<head>
	<link rel="stylesheet" href="http://corpling.uis.georgetown.edu/xrenner/css/renner.css" type="text/css" charset="utf-8"/>
	<link rel="stylesheet" href="https://corpling.uis.georgetown.edu/xrenner/css/font-awesome-4.2.0/css/font-awesome.min.css"/>
</head>
<body'''+rtl_style+'''>
<script src="http://corpling.uis.georgetown.edu/xrenner/script/jquery-1.11.3.min.js"></script>
<script src="http://corpling.uis.georgetown.edu/xrenner/script/chroma.min.js"></script>
<script src="http://corpling.uis.georgetown.edu/xrenner/script/xrenner.js"></script>
'''
	for out_tok in conll_tokens:
		if int(out_tok.id) in markstart_dict:
			for out_mark in sorted(markstart_dict[int(out_tok.id)], key=operator.attrgetter('end'), reverse=True):
				info_string = "class: " + str(out_mark.entity) + " | subclass: " + str(out_mark.subclass) + \
				              "&#10;definiteness: " + str(out_mark.definiteness) + " | agree: " + str(out_mark.agree) + \
				              "&#10;cardinality: " + str(out_mark.cardinality) + " | form: "+ str(out_mark.form) + \
				              "&#10;core_text: " + str(out_mark.core_text) + " | lemma: "+ str(out_mark.lemma)
				if out_mark.speaker != "":
					info_string += "&#10;speaker: " + out_mark.speaker
				if not out_mark.antecedent == "none":
					info_string += '&#10;coref_type: ' + out_mark.coref_type
				output_string += '<div id="' + out_mark.id + '" head="' + out_mark.head.id + '" onmouseover="highlight_group(' + \
				"'" + str(out_mark.group) + "'" + ')" onmouseout="unhighlight_group(' + "'" + str(out_mark.group) + "'" + ')" class="referent" group="' + str(out_mark.group) + '" title="' + info_string
				if not out_mark.antecedent == "none":
					output_string += '" antecedent="' + out_mark.antecedent.id
				output_string += '"><span class="entity_type">' + get_glyph(out_mark.entity) + '</span>\n'
		if int(out_tok.id) > 0:
			output_string += out_tok.text.replace("-RRB-", ")").replace("-LRB-", "(").replace("-LSB-", "[").replace("-RSB-", "]") + "\n"
		if int(out_tok.id) in markend_dict:
			for out_mark in markend_dict[int(out_tok.id)]:
				output_string += "</div>\n"
	output_string += '<script>colorize();</script>\n'
	output_string += '''</body>
</html>'''
	return output_string


def output_PAULA(conll_tokens, markstart_dict, markend_dict, docname, docpath):
	"""
	Outputs analysis results as PAULA standoff XML. Separate files for tokens, markables and coreference links
	plus annotations. This format is the most complete, distinguishing apposition, anaphora, cataphora and other
	coreference types as edge annotations.
	
	:param conll_tokens: List of all processed ParsedToken objects in the document
	:param markstart_dict: Dictionary from markable starting token ids to Markable objects
	:param markend_dict: Dictionary from markable ending token ids to Markable objects
	:return: void
	"""

	paula_text = ""
	paula_tokens = ""
	paula_markables = ""
	paula_entities = ""
	paula_rels = ""
	paula_rel_annos = ""
	cursor = 1
	rel_id = 1
	paula_text_header = '''<?xml version="1.0" standalone="no"?>
<!DOCTYPE paula SYSTEM "paula_text.dtd">

<paula version="1.0">
<header paula_id="renner.out_text" type="text"/>

<body>
'''
	paula_tok_header = '''<?xml version="1.0" standalone="no"?>

<!DOCTYPE paula SYSTEM "paula_mark.dtd">
<paula version="1.0">

<header paula_id="renner.out_tok"/>

<markList xmlns:xlink="http://www.w3.org/1999/xlink" type="tok" xml:base="xrenner.''' + docname + '''.text.xml">
'''

	paula_mark_header = '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE paula SYSTEM "paula_mark.dtd">
<paula version="1.0">

<header paula_id="xrenner.''' + docname + '''_referentSeg"/>

<markList xmlns:xlink="http://www.w3.org/1999/xlink" type="referentSeg" xml:base="xrenner.''' + docname + '''.tok.xml">
'''

	paula_entity_header = '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>

<!DOCTYPE paula SYSTEM "paula_feat.dtd">
<paula version="1.0">

<header paula_id="xrenner.''' + docname + '''_referentSeg_entity"/>

<featList xmlns:xlink="http://www.w3.org/1999/xlink" type="entity" xml:base="xrenner.''' + docname + '''.referentSeg.xml">
'''

	paula_coref_header = '''<?xml version="1.0" standalone="no"?>

<!DOCTYPE paula SYSTEM "paula_rel.dtd">
<paula version="1.0">

<header paula_id="xrenner.''' + docname + '''.referentSeg_coref"/>

<relList xmlns:xlink="http://www.w3.org/1999/xlink" type="coref" xml:base="xrenner.''' + docname + '''.referentSeg.xml">
'''
	paula_coref_type_header = '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>

<!DOCTYPE paula SYSTEM "paula_feat.dtd">
<paula version="1.0">

<header paula_id="xrenner.''' + docname + '''.referentSeg_coref_type"/>

<featList xmlns:xlink="http://www.w3.org/1999/xlink" type="type" xml:base="xrenner.''' + docname + '''.referentSeg_coref.xml">
'''

	if not os.path.exists(docpath + os.sep + docname):
		os.makedirs(docpath + os.sep + docname)
	elif os.path.isfile(docpath + os.sep + docname):
		raise("Unable to create document directory. There is already a file named " + docpath + os.sep + docname + "\n")

	f = open(docpath + os.sep + docname + os.sep + 'xrenner.' + docname + '.text.xml', 'w')
	f.write(paula_text_header)
	f = open(docpath + os.sep + docname + os.sep + 'xrenner.' + docname + '.tok.xml', 'w')
	f.write(paula_tok_header)
	f = open(docpath + os.sep + docname + os.sep + 'xrenner.' + docname + '.referentSeg.xml', 'w')
	f.write(paula_mark_header)
	f = open(docpath + os.sep + docname + os.sep + 'xrenner.' + docname + '.referentSeg_entity.xml', 'w')
	f.write(paula_entity_header)
	f = open(docpath + os.sep + docname + os.sep + 'xrenner.' + docname + '.referentSeg_coref.xml', 'w')
	f.write(paula_coref_header)
	f = open(docpath + os.sep + docname + os.sep + 'xrenner.' + docname + '.referentSeg_coref_type.xml', 'w')
	f.write(paula_coref_type_header)

	del conll_tokens[0]
	for out_tok in conll_tokens:
		paula_text += out_tok.text + " "
		if int(out_tok.id) in markstart_dict:
			for out_mark in markstart_dict[int(out_tok.id)]:
				if out_mark.end > out_mark.start:
					paula_markables += '<mark id="' + out_mark.id + '"  xlink:href="#xpointer(id(' + "'tok_" + str(out_mark.start) + "')/range-to(id('tok_" + str(out_mark.end) + "')))" + '"><!-- ' + out_mark.text + " -->\n"
				else:
					paula_markables += '<mark id="' + out_mark.id + '"  xlink:href="#tok_' + str(out_mark.start) + '"><!-- ' + out_mark.text + " -->\n"
				paula_entities += '<feat xlink:href="#' + out_mark.id + '" value="' + out_mark.entity + '"><!-- ' + out_mark.text + " -->\n"
				if out_mark.antecedent != "none":
					paula_rels += '<rel id="rel_' + str(rel_id) + '" xlink:href="#' + out_mark.id + '" target="#' + out_mark.antecedent.id + '"/><!-- ' + out_mark.text + ' ... ' + out_mark.antecedent.text + ' -->\n'
					paula_rel_annos += '<feat xlink:href="#rel_' + str(rel_id) + '" value="' + out_mark.coref_type + '"/><!-- ' + out_mark.text + ' ... ' + out_mark.antecedent.text + ' -->\n'
					rel_id += 1

		paula_tokens += '<mark id="tok_' + out_tok.id + '" xlink:href="#xpointer(string-range(//body,' + "'', " + str(cursor) + "," + str(len(out_tok.text)) + "))" + '"/><!-- ' + out_tok.text + " -->\n"
		cursor += len(out_tok.text) + 1
	
	paula_text += "\n</body>\n</paula>\n"
	paula_tokens += "</markList>\n</paula>\n"
	paula_markables += "</markList>\n</paula>\n"
	paula_entities += "</featList>\n</paula>\n"
	paula_rels += "</relList>\n</paula>\n"
	paula_rel_annos += "</featList>\n</paula>\n"
	f = open(docpath + os.sep + docname + os.sep + 'xrenner.' + docname + '.text.xml', 'a')
	f.write(paula_text)
	f = open(docpath + os.sep + docname + os.sep + 'xrenner.' + docname + '.tok.xml', 'a')
	f.write(paula_tokens)
	f = open(docpath + os.sep + docname + os.sep + 'xrenner.' + docname + '.referentSeg.xml', 'a')
	f.write(paula_markables)
	f = open(docpath + os.sep + docname + os.sep + 'xrenner.' + docname + '.referentSeg_entity.xml', 'a')
	f.write(paula_entities)
	f = open(docpath + os.sep + docname + os.sep + 'xrenner.' + docname + '.referentSeg_coref.xml', 'a')
	f.write(paula_rels)
	f = open(docpath + os.sep + docname + os.sep + 'xrenner.' + docname + '.referentSeg_coref_type.xml', 'a')
	f.write(paula_rel_annos)


def output_webanno(conll_tokens, markables):
	output = '''<?xml version="1.0" encoding="UTF-8"?>
	<xmi:XMI xmlns:cas="http:///uima/cas.ecore"
	    xmlns:type2="http:///de/tudarmstadt/ukp/dkpro/core/api/metadata/type.ecore"
	    xmlns:dependency="http:///de/tudarmstadt/ukp/dkpro/core/api/syntax/type/dependency.ecore"
	    xmlns:type5="http:///de/tudarmstadt/ukp/dkpro/core/api/syntax/type.ecore"
	    xmlns:type3="http:///de/tudarmstadt/ukp/dkpro/core/api/ner/type.ecore"
	    xmlns:custom="http:///webanno/custom.ecore"
	    xmlns:type4="http:///de/tudarmstadt/ukp/dkpro/core/api/segmentation/type.ecore"
	    xmlns:tcas="http:///uima/tcas.ecore"
	    xmlns:tweet="http:///de/tudarmstadt/ukp/dkpro/core/api/lexmorph/type/pos/tweet.ecore"
	    xmlns:chunk="http:///de/tudarmstadt/ukp/dkpro/core/api/syntax/type/chunk.ecore"
	    xmlns:xmi="http://www.omg.org/XMI"
	    xmlns:type="http:///de/tudarmstadt/ukp/dkpro/core/api/coref/type.ecore"
	    xmlns:morph="http:///de/tudarmstadt/ukp/dkpro/core/api/lexmorph/type/morph.ecore"
	    xmlns:constituent="http:///de/tudarmstadt/ukp/dkpro/core/api/syntax/type/constituent.ecore"
	    xmlns:pos="http:///de/tudarmstadt/ukp/dkpro/core/api/lexmorph/type/pos.ecore" xmi:version="2.0">
	    <cas:NULL xmi:id="0"/>
	    <cas:Sofa xmi:id="12000" sofaNum="1" sofaID="_InitialView" mimeType="text"
	        sofaString="'''

	text_string = ""
	all_ids_string = ""
	text_length = 0
	for token in conll_tokens:
		if token.text == '"':
			text_string += "&quot; "
			text_length += 2
		elif token.text == '>':
			text_string += "&gt; "
			text_length += 2
		elif token.text == '<':
			text_string += "&lt; "
			text_length += 2
		else:
			text_string += token.text + " "
			text_length += len(token.text) + 1

	output += text_string
	output += '"/>\n<type2:DocumentMetaData xmi:id="10001" sofa="12000" begin="0" end="' + str(text_length - 1) + '"'
	output += '''
		language="x-unspecified"
        documentTitle="renner_out.tcf" documentId="renner_out"
        documentUri="file:/srv/webanno/repository/project/2/document/4/source/renner_out.tcf"
        collectionId="file:/srv/webanno/repository/project/2/document/4/source/"
        documentBaseUri="file:/srv/webanno/repository/project/2/document/4/source/"
        isLastSegment="false"/>\n'''

	cursor = 0
	current_sent = 1
	sent_begin = 0
	sentences_string = ""
	tok_starts = []
	tok_ends = []

	for token in conll_tokens:
		output += '\t<type4:Token xmi:id="' + str(int(token.id) + 1) + '" sofa="12000" begin="' + str(cursor) + '" end="' + str(cursor + len(token.text)) + '"/>\n'
		all_ids_string += str(int(token.id) + 1) + " "
		tok_starts.append(cursor)
		tok_ends.append(cursor + len(token.text))

		if token.sentence.sent_num > current_sent:
			sentences_string += '\t<type4:Sentence xmi:id="' + str(4000 + current_sent) + '" sofa="12000" begin="' + str(sent_begin) + '" end="' + str(cursor - 1) + '"/>\n'
			all_ids_string += str(4000 + current_sent) + " "
			current_sent += 1
			sent_begin = cursor
		cursor += len(token.text) + 1

	sentences_string += '\t<type4:Sentence xmi:id="' + str(4000 + current_sent) + '" sofa="12000" begin="' + str(sent_begin) + '" end="' + str(cursor - 1) + '"/>\n'
	all_ids_string += str(4000 + current_sent) + " "

	output += sentences_string

	mark_counter = 1
	mark_xmi_ids = {}
	for mark in markables:
		output += '\t<custom:Referent xmi:id="' + str(5000 + mark_counter) + '" sofa="12000" begin="' + str(tok_starts[mark.start - 1]) + \
		          '" end="' + str(tok_ends[mark.end - 1]) + '" entity="' + mark.entity + '" infstat="' + mark.infstat + '"/>\n'
		all_ids_string += str(5000 + mark_counter) + " "
		mark_xmi_ids[mark.id] = str(5000 + mark_counter)
		mark_counter += 1

	link_counter = 1
	for mark in markables:
		if mark.antecedent != "none":
			output += '\t<custom:Coref xmi:id="' + str(6000 + link_counter) + '" sofa="12000" begin="' + \
			             str(min(tok_starts[mark.start - 1], tok_starts[int(mark.antecedent.start)-1])) + '" end="' + \
			             str(max(tok_ends[mark.end-1], tok_starts[int(mark.antecedent.end)-1])) + '" Dependent="' + mark_xmi_ids[mark.antecedent.id] \
			             + '" Governor="' + mark_xmi_ids[mark.id] + '" type="' + mark.coref_type + '"/>\n'
			all_ids_string += str(6000 + link_counter) + " "
			link_counter += 1

	output += '''    <type2:TagsetDescription xmi:id="15571" sofa="12000" begin="0" end="0"
        layer="de.tudarmstadt.ukp.dkpro.core.api.syntax.type.dependency.Dependency" name="Tiger"/>
    <type2:TagsetDescription xmi:id="15578" sofa="12000" begin="0" end="0"
        layer="de.tudarmstadt.ukp.dkpro.core.api.ner.type.NamedEntity" name="NER_WebAnno"/>
    <type2:TagsetDescription xmi:id="15585" sofa="12000" begin="0" end="0"
        layer="de.tudarmstadt.ukp.dkpro.core.api.lexmorph.type.pos.POS" name="STTS"/>
		<type2:TagsetDescription xmi:id="15592" sofa="12000" begin="0" end="0" layer="webanno.custom.Coref"
			name="coref_tags"/>
		<type2:TagsetDescription xmi:id="15599" sofa="12000" begin="0" end="0"
			layer="webanno.custom.Referent" name="infstat_tags"/>\n'''

	output += '<cas:View sofa="12000" members="' + all_ids_string.strip() + '"/>\n</xmi:XMI>\n'

	return output


def get_glyph(entity_type):
	"""
	Generates appropriate Font Awesome icon strings based on entity type strings, such as
	a person icon (fa-male) for the 'person' entity, etc.
	
	:param entity_type: String specifying the entity type to be visualized
	:return: HTML string with the corresponding Font Awesome icon
	"""
	if entity_type == "person":
		return '<i title="' + entity_type + '" class="fa fa-male"></i>'
	elif entity_type == "place":
		return '<i title="' + entity_type + '" class="fa fa-map-marker"></i>'
	elif entity_type == "time":
		return '<i title="' + entity_type + '" class="fa fa-clock-o"></i>'
	elif entity_type == "abstract":
		return '<i title="' + entity_type + '" class="fa fa-cloud"></i>'
	elif entity_type == "quantity":
		return '<i title="' + entity_type + '" class="fa fa-sort-numeric-asc"></i>'
	elif entity_type == "organization":
		return '<i title="' + entity_type + '" class="fa fa-bank"></i>'
	elif entity_type == "object":
		return '<i title="' + entity_type + '" class="fa fa-cube"></i>'
	elif entity_type == "event":
		return '<i title="' + entity_type + '" class="fa fa-bell-o"></i>'
	elif entity_type == "animal":
		return '<i title="' + entity_type + '" class="fa fa-paw"></i>'
	elif entity_type == "plant":
		return '<i title="' + entity_type + '" class="fa fa-pagelines"></i>'
	elif entity_type == "substance":
		return '<i title="' + entity_type + '" class="fa fa-flask"></i>'
	else:
		return '<i title="' + entity_type + '" class="fa fa-question"></i>'

