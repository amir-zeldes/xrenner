import re
from collections import defaultdict, OrderedDict
from modules.xrenner_classes import Markable
from math import log

"""
Marker module for markable entity recognition. Establishes compatibility between entity features
and determines markable extension in tokens

Author: Amir Zeldes
"""


def is_atomic(mark, atoms, lex):
	"""
	Checks if nested markables are allowed within this markable
	
	:param mark: the markable to be checked for atomicity
	:param atoms: list of atomic markable text strings
	:param lex: the LexData object with gazetteer information and model settings
	:return: bool
	"""

	marktext = mark.text.strip()

	# Do not accept a markable [New] within atomic [New Zealand]
	if marktext in atoms:
		return True
	# Remove possible prefix tokens to reject [The [United] Kingdom] if [United Kingdom] in atoms
	elif remove_prefix_tokens(marktext, lex).strip() in atoms:
		return True
	# Remove possible suffix tokens to reject [[New] Zealand 's] is [New Zealand] in atoms
	elif remove_suffix_tokens(marktext, lex).strip() in atoms:
		return True
	# Combination of prefix and suffix to reject [The [United] Kingdom 's]
	elif mark.core_text in atoms:
		return True
	elif replace_head_with_lemma(mark) in atoms:
		return True
	# Dynamic generation of proper name pattern
	elif 0 < marktext.strip().count(" ") < 3 and marktext.strip().split(" ")[0] in lex.first_names and marktext.strip().split(" ")[-1] in lex.last_names:
		return True
	else:
		non_essential_modifiers = list(mod.text for mod in mark.head.modifiers if lex.filters["non_essential_mod_func"].match(mod.func))
		if len(non_essential_modifiers) > 0:
			mark_unmod_text = mark.core_text
			for mod in non_essential_modifiers:
				mark_unmod_text = mark_unmod_text.replace(mod+" ","")
			if mark_unmod_text in lex.atoms:
				return True
		# Not an atom, nested markables allowed
		return False


def remove_suffix_tokens(marktext, lex):
	if lex.filters["core_suffixes"].search(marktext):
		return re.sub(lex.filters["core_suffixes"].pattern, " ", marktext)
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
	if lex.filters["core_prefixes"].match(marktext): # NB use initial match here
		return re.sub(lex.filters["core_prefixes"].pattern, " ", marktext)
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
	use_entity_deps = True
	if "ablations" in lex.debug:
		if "no_entity_dep" in lex.debug["ablations"]:
			use_entity_deps = False

	parent_text = token_list[int(mark.head.head)].text
	token_list[int(mark.head.id)].head_text = parent_text  # Save parent text for later dependency check
	if mark.form == "pronoun":
		if re.search(r'[12]',mark.agree):  # Explicit 1st or 2nd person pronoun
			entity = lex.filters["person_def_entity"]
			mark.entity_certainty = 'certain'
		elif mark.agree == "male" or mark.agree == "female":  # Possibly human 3rd person
			entity = lex.filters["person_def_entity"]
			mark.entity_certainty = 'uncertain'
		else:
			if parent_text in lex.entity_deps and use_entity_deps:
				if mark.head.func in lex.entity_deps[parent_text]:
					entity = max(lex.entity_deps[parent_text][mark.head.func].iterkeys(), key=(lambda key: lex.entity_deps[parent_text][mark.head.func][key]))
			else:
				entity = lex.filters["default_entity"]
				mark.entity_certainty = "uncertain"
	else:
		if entity == "":
			if re.match(r'(1[456789][0-9][0-9]|20[0-9][0-9])', mark.core_text) is not None:
				entity = lex.filters["time_def_entity"]
				mark.subclass = "time-unit" # TODO: de-hardwire this
				mark.definiteness = "def"  # literal year numbers are considered definite like 'proper names'
				mark.form = "proper"  # literal year numbers are considered definite like 'proper names'
		if entity == "":
			if re.match(r'^(([0-9]+[.,]?)+)$', mark.core_text) is not None:
				entity = lex.filters["quantity_def_entity"]
		if entity == "":
			entity = resolve_entity_cascade(mark.text.strip(), mark, lex)
		if entity == "":
			entity = resolve_entity_cascade(replace_head_with_lemma(mark), mark, lex)
		if entity == "":
			entity = resolve_entity_cascade(remove_suffix_tokens(mark.text.strip(),lex), mark, lex)
		if entity == "":
			entity = resolve_entity_cascade(remove_prefix_tokens(mark.text.strip(), lex), mark, lex)
		if entity == "":
			entity = resolve_entity_cascade(mark.core_text, mark, lex)
		if entity == "":
			entity = recognize_entity_by_mod(mark, lex)
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
					modifiers_match_definite = (lex.filters["definite_articles"].match(mod.text) is not None for mod in mark.head.modifiers)
					modifiers_match_article = (lex.filters["articles"].match(mod.text) is not None for mod in mark.head.modifiers)
					modifiers_match_def_entity = (re.sub(r"\t.*","",lex.entity_heads[mod.text.strip().lower()][0]) == lex.filters["default_entity"] for mod in mark.head.modifiers if mod.text.strip().lower() in lex.entity_heads)
					if not (any(modifiers_match_article) or any(modifiers_match_definite) or any(modifiers_match_def_entity)):
						entity = lex.filters["person_def_entity"]
		if entity == "":
			# See what the affix morphology predicts for the head
			head_text = mark.lemma if mark.lemma != "_" and mark.lemma != "" else mark.head.text
			morph_probs = get_entity_by_affix(head_text,lex)

			# Now check what the dependencies predict
			dep_probs = {}
			parent_text = token_list[int(mark.head.head)].text
			if parent_text in lex.entity_deps and use_entity_deps:
				if mark.head.func in lex.entity_deps[parent_text]:
					dep_probs.update(lex.entity_deps[parent_text][mark.head.func])

			# Compare scores to decide between affix vs. dependency evidence
			dep_values = list(dep_probs[key] for key in dep_probs)
			total_deps = float(sum(dep_values))
			probs = {}
			for key, value in dep_probs.iteritems():
				probs[key] = value/total_deps
			joint_probs = defaultdict(float)
			joint_probs.update(probs)
			for entity in morph_probs:
				joint_probs[entity] += morph_probs[entity]
			# Bias in favor of default entity to break ties
			joint_probs[lex.filters["default_entity"]] += 0.0000001

			entity = max(joint_probs.iterkeys(), key = (lambda key: joint_probs[key]))

	mark.entity = entity


def resolve_entity_cascade(entity_text, mark, lex):
	# TODO: refactor repetitive handling of alt entity / and \t coding
	entity = ""
	if entity_text in lex.entities:
		entity = lex.entities[entity_text][0]
		mark.entity_certainty = "entities_match"
		for alt in lex.entities[entity_text]:
			alt_no_agree = re.sub(r"/.*", "", alt)
			if "\t" in alt_no_agree:
				mark.alt_entities.append(alt_no_agree.split("\t")[0])
				mark.alt_subclasses.append(alt_no_agree.split("\t")[1])
			else:
				mark.alt_entities.append(alt_no_agree)
	if entity_text in lex.entity_heads:
		mark.entity_certainty = "entity_heads_match"
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
				mark.entity_certainty = "names_match"
			elif not lex.filters["person_def_entity"] in mark.alt_entities:
				mark.alt_entities.append(lex.filters["person_def_entity"])
	if 0 < entity_text.count(" ") < 3:
		if entity_text.split(" ")[0] in lex.first_names and entity_text.split(" ")[-1] in lex.last_names:
			if entity_text[0].istitle() or not lex.filters["cap_names"]:
				if lex.filters["articles"].match(mark.text.split(" ")[0]) is None:
					if entity == "":
						entity = lex.filters["person_def_entity"]
						mark.agree = lex.first_names[entity_text.split(" ")[0]]
					elif not lex.filters["person_def_entity"] in mark.alt_entities:
						mark.alt_entities.append(lex.filters["person_def_entity"])

	return entity



def resolve_mark_agree(mark, lex):
	if mark.head.morph not in ["","_"]:
		mark.agree_certainty = "head_morph"
		return [mark.head.morph]
	else:
		if mark.form == "pronoun":
			if mark.text.strip() in lex.pronouns:
				return lex.pronouns[mark.text.strip()]
			elif mark.text.lower().strip() in lex.pronouns:
				return lex.pronouns[mark.text.lower().strip()]
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




def resolve_cardinality(mark,lex):
	for mod in mark.head.modifiers:
		if mod.text in lex.numbers:
			return int(lex.numbers[mod.text][0])
		elif mod.text.lower() in lex.numbers:
			return int(lex.numbers[mod.text.lower()][0])
		else:
			thousand_sep = r"\." if lex.filters["thousand_sep"] == "." else lex.filters["thousand_sep"]
			pure_number_candidate = re.sub(thousand_sep,"",mod.text)

			decimal_sep = lex.filters["decimal_sep"]
			if decimal_sep != ".":
				pure_number_candidate = re.sub(decimal_sep,".",pure_number_candidate)
			if re.match("^(\d+(\.\d+)?|(\.\d+))$",pure_number_candidate) is not None:
				return float(pure_number_candidate)
			else:
				parts = re.match("^(\d+)/(\d+)$",pure_number_candidate)
				if parts is not None: # Fraction with slash division
					numerator = float(parts.groups()[0])
					denominator = float(parts.groups()[1])
					return numerator/denominator
	return 0





def recognize_entity_by_mod(mark, lex, mark_atoms=False):
	"""
	Attempt to recognize entity type based on modifiers
	
	:param mark: Markable for which to identify the entity type
	:param modifier_lexicon: The LexData object's modifier list
	:return: String (entity type, possibly including subtype and agreement)
	"""
	modifier_lexicon = lex.entity_mods
	mod_atoms = lex.mod_atoms
	for mod in mark.head.modifiers:
		modifier_tokens = [mod.text] + [construct_modifier_substring(mod)]
		while len(modifier_tokens) > 0:
			identifying_substr = ""
			for token in modifier_tokens:
				identifying_substr += token + " "
				if identifying_substr.strip() in modifier_lexicon:
					if identifying_substr.strip() in mod_atoms and mark_atoms:
						return modifier_lexicon[identifying_substr.strip()][0] + "@"
					else:
						return modifier_lexicon[identifying_substr.strip()][0]
				elif identifying_substr.lower().strip() in modifier_lexicon:
					if identifying_substr.lower().strip() in mod_atoms and mark_atoms:
						return modifier_lexicon[identifying_substr.lower().strip()][0] + "@"
					else:
						return modifier_lexicon[identifying_substr.lower().strip()][0]
			modifier_tokens.pop(0)
	return ""


def construct_modifier_substring(modifier):
	"""
	Creates a list of tokens representing a modifier and all of its submodifiers in sequence
	
	:param modifier: A ParsedToken object from the modifier list of the head of some markable
	:return: Text of that modifier together with its modifiers in sequence
	"""
	candidate_prefix = ""
	mod_dict = get_mod_ordered_dict(modifier)
	for mod_member in mod_dict:
		candidate_prefix += mod_dict[mod_member].text + " "
	return candidate_prefix.strip()


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
	"""
	Retrieves the (sub)modifiers of a modifier token
	
	:param mod: A ParsedToken object representing a modifier of the head of some markable
	:return: Recursive ordered dictionary of that modifier's own modifiers
	"""
	mod_dict = OrderedDict()
	mod_dict[int(mod.id)] = mod
	if len(mod.modifiers) > 0:
		for mod2 in mod.modifiers:
			mod_dict.update(get_mod_ordered_dict(mod2))
	else:
		return mod_dict
	return OrderedDict(sorted(mod_dict.items()))


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
	score = 0
	entity = ""
	probs = {}
	for i in range(1, len(head_text) - 1):
		candidates = 0
		if head_text[i:] in lex.morph:
			options = lex.morph[head_text[i:]]
			for key, value in options.items():
				candidates += value
				entity = key.split("/")[0]
				probs[entity] = float(value)
			for entity in probs:
				probs[entity] = probs[entity] / candidates
		if entity != "":
			return probs
	return probs


def pos_func_combo(pos, func, pos_func_heads_string):
	"""
	:return: bool
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
	head = re.escape(mark.head.text)
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

	core_text = marktext.strip()
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
	if end < len(conll_tokens) - 1:
		next_id = end + 1
		if markable_extend_punctuation(marktext, conll_tokens[next_id], lex.open_close_punct, "trailing"):
			marktext += conll_tokens[next_id].text + " "
			end += 1
	if start != "1":
		prev_id = start - 1
		if markable_extend_punctuation(marktext, conll_tokens[prev_id], lex.open_close_punct_rev, "leading"):
			marktext = conll_tokens[prev_id].text + " " + marktext
			start -= 1

	this_markable = Markable("", tok, "", "", start, end, core_text, core_text, "", "", "", "new", "", sentence, "none", "none", 0, [], [], [])
	# DEBUG POINT
	if this_markable.text == lex.debug["ana"]:
		pass
	this_markable.core_text = remove_suffix_tokens(remove_prefix_tokens(this_markable.core_text,lex),lex)
	while this_markable.core_text != core_text:  # Potentially repeat affix stripping as long as core text changes
		core_text = this_markable.core_text
		this_markable.core_text = remove_suffix_tokens(remove_prefix_tokens(this_markable.core_text,lex),lex)
	if this_markable.core_text == '':  # Check in case suffix removal has left no core_text
		this_markable.core_text = marktext.strip()
	this_markable.text = marktext  # Update core_text with potentially modified markable text
	return this_markable


def lookup_has_entity(text, lemma, entity, lex):
	"""
	Checks if a certain token text or lemma have the specific entity listed in the entities or entity_heads lists
	
	:param text: text of the token
	:param lemma: lemma of the token
	:param entity: entity to check for
	:param lex: the LexData object with gazetteer information and model settings
	:return: bool
	"""
	found = []
	if text in lex.entities:
		found = [i for i, x in enumerate(lex.entities[text]) if re.search(entity + '\t', x)]
	elif lemma in lex.entities:
		found = [i for i, x in enumerate(lex.entities[lemma]) if re.search(entity + '\t', x)]
	elif text in lex.entity_heads:
		found = [i for i, x in enumerate(lex.entity_heads[text]) if re.search(entity + '\t', x)]
	elif lemma in lex.entity_heads:
		found = [i for i, x in enumerate(lex.entity_heads[lemma]) if re.search(entity + '\t', x)]
	return len(found) > 0


def assign_coordinate_entity(mark,markables_by_head):
	"""
	Checks if all constituents of a coordinate markable have the same entity and subclass
	
	and if so, propagates these to the coordinate markable.
	:param mark: a coordinate markable to check the entities of its constituents
	:param markables_by_head: dictionary of markables by head id
	:return: void
	"""

	sub_entities = []
	sub_subclasses = []
	for m_id in mark.submarks:
		if m_id in markables_by_head:
			sub_entities.append(markables_by_head[m_id].entity)
			sub_subclasses.append(markables_by_head[m_id].subclass)
	if len(set(sub_entities)) == 1:  # There is agreement on the entity
		mark.entity = sub_entities[0]
	if len(set(sub_subclasses)) == 1:  # There is agreement on the entity
		mark.subclass = sub_subclasses[0]


