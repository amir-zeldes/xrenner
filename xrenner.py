#!/usr/bin/python

"""
xrenner - eXternally configurable REference and Non Named Entity Recognizer
Main controller script for entity recognition and coreference resolution
Author: Amir Zeldes
"""

from collections import defaultdict, OrderedDict
import argparse
from modules.xrenner_out import *
from modules.xrenner_classes import *
from modules.xrenner_coref import *
from modules.xrenner_lex import *

__version__ = "1.0.2"
xrenner_version = "xrenner V" + __version__

sys.dont_write_bytecode = True

def find_antecedent(markable, previous_markables, lex):
	candidate = None
	for rule in lex.coref_rules:
		if candidate is None:
			if coref_rule_applies(lex, rule[0], markable):
				candidate = search_prev_markables(markable, previous_markables, rule[1], lex, int(rule[2]), rule[3])

	return candidate


def process_sentence(conll_tokens, tokoffset, sentence):
	global children
	global markstart_dict
	global markend_dict
	global sentlength
	global markcounter
	global markables
	global sent_num
	global markables_by_head
	global groupcounter
	mark_candidates_by_head = collections.OrderedDict()
	stop_ids = {}
	for tok1 in conll_tokens[tokoffset + 1:]:
		stop_ids[tok1.id] = False  # Assume all tokens are head candidates

	# Post-process parser input based on entity list
	if lex.filters["postprocess_parser"]:
		for tok1 in conll_tokens[tokoffset + 1:]:
			if tok1.text == "-LSB-" or tok1.text == "-RSB-":
				tok1.pos = tok1.text
				tok1.func = "punct"
				tok1.head = "0"
			if lex.filters["mark_head_pos"].match(tok1.pos) is not None:
				entity_candidate = tok1.text + " "
				for tok2 in conll_tokens[int(tok1.id) + 1:]:
					if lex.filters["mark_head_pos"].match(tok2.pos) is not None:
						entity_candidate += tok2.text + " "
						### DEBUG BREAKPOINT ###
						if entity_candidate.strip() in lex.debug:
							pass
						if entity_candidate.strip() in lex.entities:  # Entity matched, check if all tokens are inter-connected
							for tok3 in conll_tokens[int(tok1.id):int(tok2.id)]:
								# Ensure right most token has head outside entity:
								if int(tok2.head) > int(tok2.id) or int(tok2.head) < int(tok1.id):
									if (int(tok3.head) < int(tok1.id) or int(tok3.head) > int(tok2.id)) and tok3.id in children[tok3.head]:
										children[tok3.head].remove(tok3.id)
										tok3.head = tok2.id
										children[tok3.head].append(tok3.id)
										break
					else:
						break
			# Check for apposition pointing back to immediately preceding proper noun token -
			# typical (German model) MaltParser name behavior
			if lex.filters["apposition_func"].match(tok1.func) is not None and not tok1.id == "1":
				if lex.filters["proper_pos"].match(conll_tokens[int(tok1.id) - 1].pos) is not None and conll_tokens[
							int(tok1.id) - 1].id == tok1.head:
					tok1.func = "xrenner_fix"
					children[str(int(tok1.id) - 1)].append(tok1.id)
					stop_ids[tok1.id] = True

			# Check for markable projecting beyond an apposition to itself and remove from children on violation
			if lex.filters["apposition_func"].match(tok1.func) is not None and not tok1.id == "1":
				for tok2 in conll_tokens[int(tok1.id) + 1:]:
					if tok2.head == tok1.head and lex.filters["non_link_func"].match(tok2.func) is None and tok2.id in children[tok2.head]:
						children[tok2.head].remove(tok2.id)


	# Expand children list recursively into descendants
	for parent_key in children:
		descendants[parent_key] = get_descendants(parent_key, children)

	# Revert conj token function to parent function
	for token in conll_tokens[tokoffset:]:
		if lex.filters["conjunct_func"].match(token.func) is not None:
			token.func = conll_tokens[int(token.head)].func
			token.head = conll_tokens[int(token.head)].head

	# Enrich tokens with modifiers
	for token in conll_tokens[tokoffset:]:
		for child in children[token.id]:
			if lex.filters["mod_func"].match(conll_tokens[int(child)].func) is not None:
				token.modifiers.append(conll_tokens[int(child)])

	# Find dead areas
	for tok1 in conll_tokens[tokoffset + 1:]:
		# Affix tokens can't be markable heads - assume parser error and fix if desired
		if lex.filters["postprocess_parser"]:
			if ((lex.filters["mark_head_pos"].match(tok1.pos) is not None and lex.filters["mark_forbidden_func"].match(tok1.func) is None) or
			pos_func_combo(tok1.pos, tok1.func, lex.filters["pos_func_heads"])) and not (stop_ids[tok1.id]):
				if tok1.text.strip() in lex.affix_tokens:
					stop_ids[tok1.id] = True
					for child_id in sorted(children[tok1.id], reverse=True):
						child = conll_tokens[int(child_id)]
						if ((lex.filters["mark_head_pos"].match(child.pos) is not None and lex.filters["mark_forbidden_func"].match(child.func) is None) or
						pos_func_combo(child.pos, child.func, lex.filters["pos_func_heads"])) and not (stop_ids[child.id]):
							child.head = tok1.head
							tok1.head = child.id
							# Make the new head be the head of all children of the affix token
							for child_id2 in children[tok1.id]:
								if not child_id2 == child_id:
									conll_tokens[int(child_id2)].head = child.id
									children[tok1.id].remove(child_id2)
									children[child.id].append(child_id2)
							# Assign the function of the affix head to the new head and vice versa
							temp_func = child.func
							child.func = tok1.func
							tok1.func = temp_func
							children[tok1.id].remove(child.id)
							children[child.id].append(tok1.id)
							# Only do this for the first subordinate markable head found by traversing right to left
							break

		# Try to construct a longer stop candidate starting with each token in the sentence
		stop_candidate = ""
		for tok2 in conll_tokens[int(tok1.id):]:
			stop_candidate += tok2.text + " "
			if stop_candidate.strip().lower() in lex.stop_list:  # Stop list matched, flag tokens as impossible markable heads
				for tok3 in conll_tokens[int(tok1.id):int(tok2.id) + 1]:
					stop_ids[tok3.id] = True

	# Find last-first name combinations
	for tok1 in conll_tokens[tokoffset + 1:-1]:
		tok2 = conll_tokens[int(tok1.id) + 1]
		if tok1.text in lex.first_names and tok2.text in lex.last_names and tok1.head == tok2.id:
			stop_ids[tok1.id] = True
	# Allow one intervening token, e.g. for middle initial
	for tok1 in conll_tokens[tokoffset + 1:-2]:
		tok2 = conll_tokens[int(tok1.id) + 2]
		if tok1.text in lex.first_names and tok2.text in lex.last_names and tok1.head == tok2.id:
			stop_ids[tok1.id] = True

	keys_to_pop = []

	# Find markables
	for tok in conll_tokens[tokoffset + 1:]:
		# Markable heads should match specified pos or pos+func combinations,
		# ruling out stop list items with appropriate functions
		if tok.text.strip() in lex.debug:
			pass
		# TODO: consider switch for lex.filters["stop_func"].match(tok.func)
		if ((lex.filters["mark_head_pos"].match(tok.pos) is not None and lex.filters["mark_forbidden_func"].match(tok.func) is None) or
			    pos_func_combo(tok.pos, tok.func, lex.filters["pos_func_heads"])) and not (stop_ids[tok.id]):
			if tok.id in descendants:
				tokenspan = descendants[tok.id] + [tok.id]
				tokenspan = map(int, tokenspan)
				tokenspan.sort()
				marktext = ""
				start = min(tokenspan)
				end = max(tokenspan)
				for span_token in conll_tokens[start:end + 1]:
					marktext += span_token.text + " "
			else:
				marktext = tok.text
				start = int(tok.id)
				end = int(tok.id)
			# Check for a trailing coordinating conjunction on a descendant of the head and re-connect if necessary
			if end < len(conll_tokens) - 1:
				coord = conll_tokens[end + 1]
				if lex.filters["coord_func"].match(coord.func) is not None and not coord.head == tok.id and int(
						coord.head) >= start:
					conjunct1 = conll_tokens[int(conll_tokens[end + 1].head)]
					for tok2 in conll_tokens[end + 1:]:
						if (tok2.head == conjunct1.head and tok2.func == conjunct1.func) or tok2.head == coord.id:
							conjunct2 = tok2
							tokenspan = [conjunct2.id, str(end)]
							if conjunct2.id in descendants:
								tokenspan += descendants[conjunct2.id]
							tokenspan = map(int, tokenspan)
							tokenspan.sort()
							end = max(tokenspan)
							marktext = ""
							for span_token in conll_tokens[start:end + 1]:
								marktext += span_token.text + " "
							break

			core_text = marktext
			# Extend markable to 'affix tokens'
			if marktext.strip() in lex.debug:
				pass
			# Do not extend pronouns or stop functions
			if lex.filters["stop_func"].match(tok.func) is None and lex.filters["pronoun_pos"].match(tok.pos) is None:
				extend_affixes = markable_extend_affixes(start, end, conll_tokens, tokoffset + 1, lex)
				if not extend_affixes[0] == 0:
					if extend_affixes[0] < start:
						prefix_text = ""
						for prefix_tok in conll_tokens[extend_affixes[0]:extend_affixes[1]]:
							prefix_text += prefix_tok.text + " "
							keys_to_pop.append(prefix_tok.id)
							start -= 1
						marktext = prefix_text + marktext
					else:
						for suffix_tok in conll_tokens[extend_affixes[0]:extend_affixes[1]]:
							keys_to_pop.append(suffix_tok.id)
							marktext += suffix_tok.text + " "
							end += 1

			# Extend markable to trailing closing punctuation if it contains opening punctuation
			if int(tok.id) < len(conll_tokens) - 1:
				next_id = int(tok.id) + 1
				if markable_extend_punctuation(marktext, conll_tokens[next_id], lex.open_close_punct):
					marktext += conll_tokens[next_id].text + " "
					end += 1

			this_markable = Markable("", tok, conll_tokens[int(tok.head)], "", start, end, core_text, "", "", "", "new", "", sentence, "none", "none", 0, [], [], [])
			this_markable.text = marktext  # Update core_text with potentially modified markable text
			mark_candidates_by_head[tok.id] = this_markable

	for mark_id in mark_candidates_by_head:
		mark = mark_candidates_by_head[mark_id]
		if is_atomic(mark, lex.atoms, lex):
			for index in enumerate(mark_candidates_by_head):
				key = index[1]
				if key != mark.head.id and mark.start <= int(key) <= mark.end and int(key):
					keys_to_pop.append(key)
		elif len(recognize_prefix(mark, lex.entity_mods)) > 1:
			stoplist_prefix_tokens(mark, lex.entity_mods, keys_to_pop)

	for key in keys_to_pop:
		mark_candidates_by_head.pop(key, None)

	for mark_id in mark_candidates_by_head:
		mark = mark_candidates_by_head[mark_id]
		if mark.text.strip() in lex.debug:
			pass
		tok = mark.head
		if lex.filters["proper_pos"].match(tok.pos) is not None:
			mark.form = "proper"
		elif lex.filters["pronoun_pos"].match(tok.pos) is not None:
			mark.form = "pronoun"
		elif tok.text in lex.pronouns:
			mark.form = "pronoun"
		else:
			mark.form = "common"

		definiteness = "def"

		mark.alt_agree = resolve_mark_agree(mark, lex)
		if mark.alt_agree is not None:
			mark.agree = mark.alt_agree[0]
		else:
			mark.alt_agree = []

		if mark.agree != mark.head.morph and mark.head.morph != "_" and mark.head.morph != "--":
			mark.agree = mark.head.morph
			mark.alt_agree.append(mark.head.morph)

		resolve_mark_entity(mark, lex)
		if "/" in mark.entity:  # Lexicalized agreement information appended to entity
			if mark.agree == "" or mark.agree is None:
				mark.agree = mark.entity.split("/")[1]
			else:
				mark.alt_agree.append(mark.entity.split("/")[1])
			mark.entity = mark.entity.split("/")[0]
		elif mark.entity == lex.filters["person_def_entity"] and mark.agree == lex.filters["default_agree"]:
			mark.agree = lex.filters["person_def_agree"]
		subclass = ""
		if "\t" in mark.entity:  # This is a subclass baring solution
			subclass = mark.entity.split("\t")[1]
			mark.entity = mark.entity.split("\t")[0]
		if mark.entity == lex.filters["person_def_entity"] and mark.form != "pronoun":
			if mark.text.strip() in lex.names:
				mark.agree = lex.names[mark.text.strip()]
		if mark.entity == lex.filters["person_def_entity"] and mark.agree is None:
			no_affix_mark = remove_suffix_tokens(remove_prefix_tokens(mark.text, lex), lex)
			if no_affix_mark in lex.names:
				mark.agree = lex.names[no_affix_mark]
		if mark.entity == lex.filters["person_def_entity"] and mark.agree is None:
			mark.agree = lex.filters["person_def_agree"]
		if mark.form == "pronoun" and (mark.entity == "abstract" or mark.entity == ""):
			if mark.head.head in markables_by_head and lex.filters["subject_func"].match(mark.head.func) is not None:
				mark.entity = markables_by_head[mark.head.head].entity
		if mark.entity == "" and mark.core_text.upper() == mark.core_text:  # Unknown all caps entity, guess acronym default
			mark.entity = lex.filters["all_caps_entity"]
			mark.entity_certainty = "uncertain"
		if mark.entity == "" and mark.form != "pronoun":  # Unknown entity, guess by affix
			mark.entity = get_entity_by_affix(mark.head.lemma.strip(), lex)
			mark.entity_certainty = "uncertain"
		if mark.entity == "":  # Unknown entity, guess default
			mark.entity = lex.filters["default_entity"]
			mark.entity_certainty = "uncertain"
		if subclass == "":
			subclass = mark.entity

		markcounter += 1
		groupcounter += 1
		this_markable = Markable("referent_" + str(markcounter), tok, mark.form,
		                         definiteness, mark.start, mark.end, mark.text, mark.entity, mark.entity_certainty,
		                         subclass, "new", mark.agree, mark.sentence, "none", "none", groupcounter,
		                         mark.alt_entities, mark.alt_subclasses, mark.alt_agree)
		markables.append(this_markable)
		markables_by_head[tok.id] = this_markable
		markstart_dict[this_markable.start].append(this_markable)
		markend_dict[this_markable.end].append(this_markable)

	for markable_head_id in markables_by_head:
		if int(markable_head_id) > tokoffset:  # Resolve antecedent for current sentence markables
			current_markable = markables_by_head[markable_head_id]
			if current_markable.text.strip() in lex.debug:
				pass
			if antecedent_prohibited(current_markable, conll_tokens, lex):
				antecedent = None
			else:
				antecedent = find_antecedent(current_markable, markables, lex)
			if antecedent is not None:
				if int(antecedent.head.id) < int(current_markable.head.id):
					current_markable.antecedent = antecedent
					current_markable.group = antecedent.group
					if lex.filters["apposition_func"].match(current_markable.head.func) is not None:
						current_markable.coref_type = "appos"
					elif current_markable.form == "pronoun":
						current_markable.coref_type = "ana"
					elif current_markable.coref_type == "none":
						current_markable.coref_type = "coref"
					current_markable.infstat = "giv"
				else:  # Cataphoric match
					antecedent.antecedent = current_markable
					antecedent.group = current_markable.group
					current_markable.coref_type = "cata"
					current_markable.infstat = antecedent.infstat
					antecedent.infstat = "giv"
			elif current_markable.form == "pronoun":
				current_markable.infstat = "acc"
			else:
				current_markable.infstat = "new"

			if current_markable.agree is not None and current_markable.agree != '':
				lex.last[current_markable.agree] = current_markable
			else:
				lex.last[lex.filters["default_agree"]] = current_markable


parser = argparse.ArgumentParser()
parser.add_argument('-o', '--output', action="store", dest="format", default="sgml", help="Output format, default: sgml; alternatives: html, paula, webanno, conll")
parser.add_argument('-m', '--model', action="store", dest="model", default="eng", help="Input model directory name, in models/")
parser.add_argument('file', action="store", help="Input file name to process")
parser.add_argument('--version', action='version', version=xrenner_version)

parser.parse_args()

options = parser.parse_args()

out_format = options.format
model = options.model
lex = LexData(model)
infile = open(options.file)

conll_tokens = []
markables = []
markables_by_head = OrderedDict()
markstart_dict = defaultdict(list)
markend_dict = defaultdict(list)
conll_tokens.append(ParsedToken(0, "ROOT", "--", "XX", "", -1, "NONE", Sentence(1, ""), [], [], lex))
tokoffset = 0
sentlength = 0
markcounter = 1
groupcounter = 1

##GLOBALS
children = defaultdict(list)
descendants = {}
child_funcs = defaultdict(list)

sent_num = 1
quoted = False
current_sentence = Sentence(sent_num, "")
for myline in infile:
	if myline.find("\t") > 0:  # Only process lines that contain tabs (i.e. conll tokens)
		cols = myline.split("\t")
		if lex.filters["open_quote"].match(cols[1]) is not None and quoted is False:
			quoted = True
		elif lex.filters["open_quote"].match(cols[1]) is not None and quoted is True:
			quoted = False
		if lex.filters["question_mark"].match(cols[1]) is not None:
			current_sentence.mood = "question"
		if cols[3] in lex.func_substitutes_forward and int(cols[6]) > int(cols[0]):
			tok_func = re.sub(lex.func_substitutes_forward[cols[3]][0],lex.func_substitutes_forward[cols[3]][1],cols[7])
		elif cols[3] in lex.func_substitutes_backward and int(cols[6]) < int(cols[0]):
			tok_func = re.sub(lex.func_substitutes_backward[cols[3]][0],lex.func_substitutes_backward[cols[3]][1],cols[7])
		else:
			tok_func = cols[7]
		conll_tokens.append(ParsedToken(str(int(cols[0]) + tokoffset), cols[1], cols[2], cols[3], cols[5],
		                                str(int(cols[6]) + tokoffset), tok_func, current_sentence, [], [], lex, quoted))
		sentlength += 1
		if not (lex.filters["non_link_func"].match(cols[7]) is not None or lex.filters["non_link_tok"].match(cols[1]) is not None):
		# Do not add a child if this is a coordinating conjunction etc.
			children[str(int(cols[6]) + tokoffset)].append(str(int(cols[0]) + tokoffset))
		child_funcs[(int(cols[6]) + tokoffset)].append(cols[7])
	elif sentlength > 0:
		# Add list of all funcs dependent on this token to its child_funcs
		for child_id in child_funcs:
			for func in child_funcs[child_id]:
				if func not in conll_tokens[child_id].child_funcs:
					conll_tokens[child_id].child_funcs.append(func)
		process_sentence(conll_tokens, tokoffset, current_sentence)
		sent_num += 1
		current_sentence = Sentence(sent_num, "")
		if sentlength > 0:
			tokoffset += sentlength

		sentlength = 0

if sentlength > 0:  # Leftover sentence did not have trailing newline
	process_sentence(conll_tokens, tokoffset, current_sentence)

postprocess_coref(markables, lex)

marks_to_kill = []
for mark in markables:
	if mark.id == "0":  # Markable has been marked for deletion
		markstart_dict[mark.start].remove(mark)
		if len(markstart_dict[mark.start]) < 1:
			del markstart_dict[mark.start]
		markend_dict[mark.end].remove(mark)
		if len(markend_dict[mark.start]) < 1:
			del markend_dict[mark.start]
		marks_to_kill.append(mark)

for mark in marks_to_kill:
	markables.remove(mark)

if out_format == "html":
	output_HTML(conll_tokens, markstart_dict, markend_dict)
elif out_format == "paula":
	output_PAULA(conll_tokens, markstart_dict, markend_dict)
elif out_format == "webanno":
	output_webanno(conll_tokens[1:], markables)
elif out_format == "conll":
	output_conll(conll_tokens, markstart_dict, markend_dict, options.file)
else:
	output_SGML(conll_tokens, markstart_dict, markend_dict)

