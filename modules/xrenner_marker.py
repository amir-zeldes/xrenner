import re
import collections
from modules.xrenner_classes import Markable

"""
xrenner - eXternally configurable REference and Non Named Entity Recognizer
Marker module for markable entity recognition. Establishes compatibility between entity features
and determines markable extension in tokens
Author: Amir Zeldes
"""


def agree_compatible(mark1, mark2, lex):
	if mark1.agree == mark2.agree:
		return True
	elif lex.filters["no_person_agree"].match(mark1.agree) and mark2.entity == lex.filters["person_def_entity"]:
		return False
	elif lex.filters["no_person_agree"].match(mark2.agree) and mark1.entity == lex.filters["person_def_entity"]:
		return False
	elif mark1.agree in mark2.alt_agree:
		mark2.agree = mark1.agree
		return True
	elif mark2.agree in mark1.alt_agree:
		mark1.agree = mark2.agree
		return True
	elif (mark1.agree is None or mark1.agree == '') and (mark2.agree is None or mark2.agree == ''):
		return True
	elif (((mark1.agree is None or mark1.agree == '') and lex.filters["agree_with_unknown"].match(mark2.agree) is not None)
	or ((mark2.agree is None or mark2.agree == '') and lex.filters["agree_with_unknown"].match(mark1.agree) is not None)):
		return True
	else:
		return False


def entities_compatible(mark1, mark2, lex):
	if mark1.entity == mark2.entity:
		return True
	elif mark1.entity is None or mark2.entity is None:
		return True
	if mark1.form == "pronoun" and not (mark1.entity == lex.filters["person_def_entity"] and mark2.entity != lex.filters["person_def_entity"]):
		return True
	if mark1.entity in mark2.alt_entities and mark1.entity != mark2.entity and (mark2.entity_certainty == "uncertain" or mark2.entity_certainty == "propagated"):
		return True
	elif mark2.entity in mark1.alt_entities and mark1.entity != mark2.entity and (mark1.entity_certainty == "uncertain" or mark1.entity_certainty == "propagated"):
		return True

	return False


def merge_entities(mark1, mark2, previous_markables, lex):
	if not mark1.entity == mark2.entity:
		if mark1.entity in mark2.alt_entities:
			if update_group(mark2, mark1, previous_markables, lex):
				mark2.entity = mark1.entity
				mark2.subclass = mark1.subclass
				return True
			else:
				return False
		else:
			if update_group(mark1, mark2, previous_markables, lex):
				mark1.entity = mark2.entity
				mark1.subclass = mark2.subclass
				return True
			else:
				return False
	else:
		return True


def update_group(host, model, previous_markables, lex):
	group = host.group
	for markable in previous_markables:
		if markable.group == group:
			if incompatible_modifiers(markable, model, lex):
				return False
	for markable in previous_markables:
		if markable.group == group:
			markable.entity = model.entity
			markable.subclass = model.subclass
	return True


def incompatible_modifiers(markable, candidate, lex):
	# Check if markable and candidate have modifiers that are in the antonym list together,
	# e.g. 'the good news' should not be coreferent with 'the bad news'
	for mod in markable.head.modifiers:
		if mod.text.lower() in lex.antonyms:
			for candidate_mod in candidate.head.modifiers:
				if candidate_mod.text.lower() in lex.antonyms[mod.text.lower()]:
					markable.non_antecdent_groups.add(candidate.group)
					return True
		elif mod.lemma.lower() in lex.antonyms:
			for candidate_mod in candidate.head.modifiers:
				if candidate_mod.lemma.lower() in lex.antonyms[mod.lemma.lower()]:
					markable.non_antecdent_groups.add(candidate.group)
					return True

	# Check if markable and candidate have modifiers that are different place names
	# e.g. 'Georgetown University' is incompatible with 'Boston University' even if those entities are not in lexicon
	for mod in markable.head.modifiers:
		if mod.text.strip() in lex.entities and (mod.text.istitle() or not lex.filters["cap_names"]):
			if re.sub('\t.*', "", lex.entities[mod.text.strip()][0]) == lex.filters["place_def_entity"]:
				for candidate_mod in candidate.head.modifiers:
					if candidate_mod.text.strip() in lex.entities and (candidate_mod.text.istitle() or not lex.filters["cap_names"]):
						if re.sub('\t.*', "", lex.entities[candidate_mod.text.strip()][0]) == lex.filters["place_def_entity"]:
							markable.non_antecdent_groups.add(candidate.group)
							return True


	# Check for each possible pair of modifiers with identical function in the ident_mod list whether they are identical,
	# e.g. for the num function 'the four children' shouldn't be coreferent with 'five other children'
	for mod in markable.head.modifiers:
		for candidate_mod in candidate.head.modifiers:
			# TODO: add support for ident_mod pos func combo:
			# if lex.filters["ident_mod_func"].match(mod.func+"+"+mod.pos) and lex.filters["ident_mod_func"].match(candidate_mod.func+"+"+candidate_mod.pos) and
			# mod.text.lower != candidate_mod.text.lower():
			if lex.filters["ident_mod_func"].match(mod.func) is not None and lex.filters["ident_mod_func"].match(candidate_mod.func) is not None and mod.text.lower != candidate_mod.text.lower():
				markable.non_antecdent_groups.add(candidate.group)
				return True

	# Recursive check through antecedent ancestors in group
	if candidate.antecedent != "none":
		antecdent_incompatible = incompatible_modifiers(markable, candidate.antecedent, lex)
		if antecdent_incompatible:
			return True

	return False


def is_atomic(mark, atoms, lex):
	"""
	Checks if nested markables are allowed within this markable
	:param mark: the markable to be checked for atomicity
	:param atoms: list of atomic markable text strings
	:param lex: the LexData object with gazetteer information and model settings
	:return: bool
	"""

	marktext = mark.core_text

	# Do not accept a markable [New] within atomic [New Zealand]
	if marktext.strip() in atoms:
		return True
	# Remove possible prefix tokens to reject [The [United] Kingdom] if [United Kingdom] in atoms
	elif remove_prefix_tokens(marktext, lex).strip() in atoms:
		return True
	# Remove possible suffix tokens to reject [[New] Zealand 's] is [New Zealand] in atoms
	elif remove_suffix_tokens(marktext, lex).strip() in atoms:
		return True
	# Combination of prefix and suffix to reject [The [United] Kingdom 's]
	elif remove_prefix_tokens(remove_suffix_tokens(marktext, lex), lex).strip() in atoms:
		return True
	elif replace_head_with_lemma(mark) in atoms:
		return True
	# Dynamic generation of proper name pattern
	elif 0 < marktext.strip().count(" ") < 3 and marktext.strip().split(" ")[0] in lex.first_names and marktext.strip().split(" ")[-1] in lex.last_names:
		return True
	# Not an atom, nested markables allowed
	else:
		return False


def remove_suffix_tokens(marktext, lex):
	re_suffix_tokens = re.compile(" ('s|') ?$")
	if re_suffix_tokens.search(marktext):
		return re.sub(r" ('s|') ?$", " ", marktext)
	else:
		tokens = marktext.strip().split(" ")
		suffix_candidate = ""
		for token in reversed(tokens):
			suffix_candidate = token + " " + suffix_candidate
			if suffix_candidate.strip() in lex.affix_tokens:
				if lex.affix_tokens[suffix_candidate.strip()] == "prefix":
					return re.sub(suffix_candidate + r'$', "", marktext)
	return marktext


def remove_prefix_tokens(marktext, lex):
	re_prefix_tokens = re.compile(" ?([Tt]he|an?|some|all|many) ?")
	if re_prefix_tokens.match(marktext) is not None:
		return re.sub(r"^ ?([Tt]he|an?|some|all|many) ?", "", marktext)
	else:
		tokens = marktext.strip().split(" ")
		prefix_candidate = ""
		for token in tokens:
			prefix_candidate += token + " "
			if prefix_candidate.strip() in lex.affix_tokens:
				if lex.affix_tokens[prefix_candidate.strip()] == "prefix":
					return re.sub(r'^' + prefix_candidate, "", marktext)
	return marktext


def resolve_mark_entity(mark, token_list, lex):
	entity = ""
	if mark.form == "pronoun":
		if mark.agree == "male" or mark.agree == "female":
			entity = lex.filters["person_def_entity"]
			mark.alt_entities.append("animal")
			mark.entity_certainty = 'uncertain'
		else:
			entity = resolve_entity_cascade(mark.core_text.strip(), mark, lex)
	else:
		if entity == "":
			if re.match(r'(1[456789][0-9][0-9]|20[0-9][0-9])', mark.core_text) is not None:
				entity = lex.filters["time_def_entity"]
		if entity == "":
			if re.match(r'(([0-9]+[.,]?)+)', mark.core_text) is not None:
				entity = lex.filters["quantity_def_entity"]
		if entity == "":
			entity = resolve_entity_cascade(mark.core_text.strip(), mark, lex)
		if entity == "":
			entity = resolve_entity_cascade(replace_head_with_lemma(mark), mark, lex)
		if entity == "":
			entity = resolve_entity_cascade(remove_suffix_tokens(mark.core_text, lex).strip(), mark, lex)
		if entity == "":
			entity = resolve_entity_cascade(remove_prefix_tokens(mark.core_text, lex).strip(), mark, lex)
		if entity == "":
			entity = resolve_entity_cascade(remove_suffix_tokens(remove_prefix_tokens(mark.core_text, lex), lex).strip(), mark, lex)
		if entity == "":
			entity = recognize_prefix(mark, lex.entity_mods)
		if entity == "" and mark.head.text.istitle():
			entity = resolve_entity_cascade(mark.core_text.lower().strip(), mark, lex)
		if entity == "" and not mark.head.text.istitle():
			entity = resolve_entity_cascade(mark.core_text.strip()[:1].upper() + mark.core_text.strip()[1:], mark, lex)
		if entity == "":
			entity = resolve_entity_cascade(mark.head.text, mark, lex)
		if entity == "" and mark.head.text.istitle():
			entity = resolve_entity_cascade(mark.head.text.lower(), mark, lex)
		if entity == "" and mark.head.text.isupper():
			entity = resolve_entity_cascade(mark.head.text.lower(), mark, lex)
		if entity == "" and mark.head.text.isupper():
			entity = resolve_entity_cascade(mark.head.text.lower().title(), mark, lex)
		if entity == "" and not mark.head.lemma == mark.head.text:  # Try lemma match if lemma different from token
			entity = resolve_entity_cascade(mark.head.lemma, mark, lex)
		if entity == "":
			if (mark.head.text.istitle() or not lex.filters["cap_names"]):
				if mark.head.text in lex.last_names or mark.head.text in lex.first_names:
					entity = lex.filters["person_def_entity"]
	if entity == "":
		parent_text = token_list[int(mark.head.head)].text
		if parent_text in lex.entity_deps:
			if mark.head.func in lex.entity_deps[parent_text]:
				#pass
				entity = lex.entity_deps[parent_text][mark.head.func][0]

	mark.entity = entity


def resolve_entity_cascade(entity_text, mark, lex):
	# TODO: refactor repetitive handling of alt entity / and \t coding
	entity = ""
	if entity_text in lex.entities:
		entity = lex.entities[entity_text][0]
		for alt in lex.entities[entity_text]:
			alt_no_agree = re.sub(r"/.*", "", alt)
			if "\t" in alt_no_agree:
				mark.alt_entities.append(alt_no_agree.split("\t")[0])
				mark.alt_subclasses.append(alt_no_agree.split("\t")[1])
			else:
				mark.alt_entities.append(alt_no_agree)
	if entity_text in lex.entity_heads:
		if entity == "":
			entity = lex.entity_heads[entity_text][0]
			for alt in lex.entity_heads[entity_text]:
				alt_no_agree = re.sub(r"/.*", "", alt)
				if "\t" in alt:
					mark.alt_entities.append(alt_no_agree.split("\t")[0])
					mark.alt_subclasses.append(alt_no_agree.split("\t")[1])
				else:
					mark.alt_entities.append(alt_no_agree)
		else:
			for alt in lex.entity_heads[entity_text]:
				alt_no_agree = re.sub(r"/.*", "", alt)
				if "\t" in alt:
					mark.alt_entities.append(alt_no_agree.split("\t")[0])
					mark.alt_subclasses.append(alt_no_agree.split("\t")[1])
				else:
					mark.alt_entities.append(alt_no_agree)
	if entity_text in lex.names:
		if entity_text[0].istitle() or not lex.filters["cap_names"]:
			if entity == "":
				entity = lex.filters["person_def_entity"]
			elif not lex.filters["person_def_entity"] in mark.alt_entities:
				mark.alt_entities.append(lex.filters["person_def_entity"])
	if 0 < entity_text.count(" ") < 3:
		if entity_text.split(" ")[0] in lex.first_names and entity_text.split(" ")[-1] in lex.last_names:
			if entity_text[0].istitle() or not lex.filters["cap_names"]:
				if lex.filters["articles"].match(mark.core_text.split(" ")[0]) is None:
					if entity == "":
						entity = lex.filters["person_def_entity"]
						mark.agree = lex.first_names[entity_text.split(" ")[0]]
					elif not lex.filters["person_def_entity"] in mark.alt_entities:
						mark.alt_entities.append(lex.filters["person_def_entity"])
	return entity



def resolve_mark_agree(mark, lex):
	if mark.form == "pronoun":
		if mark.core_text.strip() in lex.pronouns:
			return lex.pronouns[mark.core_text.strip()]
		elif mark.core_text.lower().strip() in lex.pronouns:
			return lex.pronouns[mark.core_text.lower().strip()]
	if mark.form == "proper":
		if mark.core_text.strip() in lex.names:
			return [lex.names[mark.core_text.strip()]]
		elif mark.head.text.strip() in lex.first_names:
			return [lex.first_names[mark.head.text.strip()]]
	if mark.head.pos in lex.pos_agree_mappings:
		mark.agree_certainty = "pos_agree_mappings"
		return [lex.pos_agree_mappings[mark.head.pos]]
	elif mark.core_text.strip() in lex.entities:
		for entry in lex.entities[mark.core_text.strip()]:
			if "/" in entry:
				if mark.agree == "":
					mark.agree = entry[entry.find("/") + 1:]
				mark.alt_agree.append(entry[entry.find("/") + 1:])
	elif mark.head.text.strip() in lex.entity_heads:
		for entry in lex.entity_heads[mark.head.text.strip()]:
			if "/" in entry:
				if mark.agree == "":
					mark.agree = entry[entry.find("/") + 1:]
				mark.alt_agree.append(entry[entry.find("/") + 1:])


def recognize_prefix(mark, prefix_dict):
	"""
	Attempt to recognize entity type based on a prefix
	:param mark:
	:return: string (entity type)
	"""
	substr = ""
	candidate_prefix = ""
	for mod in mark.head.modifiers:
		mod_dict = get_mod_ordered_dict(mod)
		for mod_member in mod_dict:
			candidate_prefix += mod_dict[mod_member].text + " "
		tokens = candidate_prefix.strip().split(" ")
		for token in tokens:
			substr += token + " "
			if substr.strip() in prefix_dict:
				return prefix_dict[substr.strip()]
	return ""


def stoplist_prefix_tokens(mark, prefix_dict, keys_to_pop):
	substr = ""
	candidate_prefix = ""
	for mod in mark.head.modifiers:
		mod_dict = get_mod_ordered_dict(mod)
		for mod_member in mod_dict:
			candidate_prefix += mod_dict[mod_member].text + " "
		tokens = candidate_prefix.strip().split(" ")
		for token in tokens:
			substr += token + " "
			if substr.strip() in prefix_dict:
				tokens_affected_count = substr.count(" ")
				i = 0
				for mod_token in mod_dict:
					if i < tokens_affected_count and not mod_dict[mod_token].id == mark.head.id:
						keys_to_pop.append(mod_dict[mod_token].id)
					i += 1



def get_mod_ordered_dict(mod):
	mod_dict = collections.OrderedDict()
	mod_dict[mod.id] = mod
	if len(mod.modifiers) > 0:
		for mod2 in mod.modifiers:
			mod_dict.update(get_mod_ordered_dict(mod2))
	else:
		return mod_dict
	return collections.OrderedDict(sorted(mod_dict.items()))



def markable_extend_punctuation(marktext, adjacent_token, punct_dict, direction):
	if direction == "trailing":
		for open_punct in punct_dict:
			if open_punct in marktext and adjacent_token.text == punct_dict[open_punct]:
				return True
	else:
		for close_punct in punct_dict:
			if close_punct in marktext and adjacent_token.text == punct_dict[close_punct]:
				return True
	return False



def markables_overlap(mark1, mark2):
	if mark2.end >= mark1.start >= mark2.start and mark2.end:
		return True
	elif mark2.end >= mark1.end >= mark2.start:
		return True
	else:
		return False


def markable_extend_affixes(start, end, conll_tokens, sent_start, lex):
	candidate_affix = ""
	for tok in reversed(conll_tokens[sent_start:start]):
		candidate_affix = tok.text + " " + candidate_affix
		if candidate_affix.lower().strip() in lex.affix_tokens:
			if lex.affix_tokens[candidate_affix.lower().strip()] == "prefix":
				return [int(tok.id), int(tok.id) + candidate_affix.count(" ")]
		elif candidate_affix.strip() in lex.affix_tokens:
			if lex.affix_tokens[candidate_affix.strip()] == "prefix":
				return [int(tok.id), int(tok.id) + candidate_affix.count(" ")]
	candidate_affix = ""
	for tok in conll_tokens[end+1:]:
		candidate_affix += tok.text + " "
		if candidate_affix.lower().strip() in lex.affix_tokens:
			if lex.affix_tokens[candidate_affix.lower().strip()] == "suffix":
				return [int(tok.id) - candidate_affix.strip().count(" "), int(tok.id) + 1]
		elif candidate_affix.strip() in lex.affix_tokens:
			if lex.affix_tokens[candidate_affix.strip()] == "suffix":
				return [int(tok.id) - candidate_affix.strip().count(" "), int(tok.id) + 1]
	return [0,0]


def get_entity_by_affix(head_text, lex):
	affix_max = 0
	entity = ""
	for i in range(1, len(head_text) - 1):
		if head_text[i:] in lex.morph:
			options = lex.morph[head_text[i:]]
			for key, value in options.items():
				if value > affix_max:
					entity = key.split("/")[0]
					affix_max = value
		if entity != "":
			return entity
	return entity


def pos_func_combo(pos, func, pos_func_heads_string):
	"""
	:rtype : bool
	"""
	pos_func_heads = pos_func_heads_string.split(";")
	if pos + "+" + func in pos_func_heads:
		return True
	elif pos + "!" + func in pos_func_heads:
		return False
	else:
		if pos_func_heads_string.find(";" + pos + "!") > -1 or pos_func_heads_string.startswith(pos + "!"):
			return True
		else:
			return False


def replace_head_with_lemma(mark):
	head = mark.head.text
	lemma = mark.head.lemma
	return re.sub(head, lemma, mark.core_text).strip()


def make_markable(tok, conll_tokens, descendants, tokoffset, sentence, keys_to_pop, lex):
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
	# DEBUG POINT
	if marktext.strip() in lex.debug:
		pass
	# Extend markable to 'affix tokens'
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
		if markable_extend_punctuation(marktext, conll_tokens[next_id], lex.open_close_punct, "trailing"):
			marktext += conll_tokens[next_id].text + " "
			end += 1
	if tok.id != "1":
		prev_id = start - 1
		if markable_extend_punctuation(marktext, conll_tokens[prev_id], lex.open_close_punct_rev, "leading"):
			marktext = conll_tokens[prev_id].text + " " + marktext
			start -= 1


	this_markable = Markable("", tok, "", "", start, end, core_text, "", "", "", "new", "", sentence, "none", "none", 0, [], [], [])
	this_markable.text = marktext  # Update core_text with potentially modified markable text
	return this_markable