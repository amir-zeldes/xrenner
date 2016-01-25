from xrenner_marker import *
from xrenner_compatible import *
"""
xrenner - eXternally configurable REference and Non Named Entity Recognizer
Coreference resolution module. Iterates through markables to find possible matches based on rules.
Author: Amir Zeldes
"""


def search_prev_markables(markable, previous_markables, rule, lex, max_dist, propagate):
	candidate_list = []
	if rule.find("lookahead") > -1:
		referents_to_loop = previous_markables
	else:
		referents_to_loop = reversed(previous_markables)
	for candidate in referents_to_loop:  # loop through previous markables backwards
		#DEBUG breakpoint:
		if candidate.text.startswith("SOME TEXT"):
			pass
		if markable.sentence.sent_num - candidate.sentence.sent_num <= max_dist:
			if ((int(markable.head.id) > int(candidate.head.id) and
			rule.find("lookahead") == -1) or (int(markable.head.id) < int(candidate.head.id) and rule.find("lookahead") > -1)):
				if candidate.group not in markable.non_antecdent_groups:
					if coref_rule_applies(lex, rule, candidate, markable):
						if not markables_overlap(markable, candidate):
							if markable.form == "pronoun":
								if agree_compatible(markable, candidate, lex) or (rule.find("anyagree") > -1 and group_agree_compatible(markable,candidate,previous_markables,lex)):
									if entities_compatible(markable, candidate, lex):
										#propagate_entity(markable, candidate)
										#return candidate
										candidate_list.append(candidate)
							elif markable.text.strip() == candidate.text.strip() or (len(markable.text) > 4 and (candidate.text.lower() == markable.text.lower())):
								propagate_entity(markable, candidate, propagate)
								return candidate
							elif markable.text.strip() + "|" + candidate.text.strip() in lex.coref and entities_compatible(
									markable, candidate, lex) and agree_compatible(markable, candidate, lex):
								markable.coref_type = lex.coref[markable.text.strip() + "|" + candidate.text.strip()]
								propagate_entity(markable, candidate)
								return candidate
							elif markable.entity == candidate.entity  and agree_compatible(markable, candidate, lex) and (markable.head.text == candidate.head.text or
							(len(markable.head.text) > 4 and (candidate.head.text.lower() == markable.head.text.lower())) or
							(markable.head.lemma == candidate.head.lemma and lex.filters["lemma_match_pos"].match(markable.head.pos) is not None
							and lex.filters["lemma_match_pos"].match(candidate.head.pos) is not None)):
								if modifiers_compatible(markable, candidate, lex) and modifiers_compatible(candidate, markable, lex):
									if propagate.startswith("propagate"):
										propagate_entity(markable, candidate, propagate)
									return candidate
							elif markable.entity == candidate.entity and (isa(markable, candidate, lex) or isa(candidate, markable, lex)):
								if modifiers_compatible(markable, candidate, lex) and modifiers_compatible(candidate, markable, lex):
									if propagate.startswith("propagate"):
										propagate_entity(markable, candidate, propagate)
									return candidate
							elif (markable.head.text == candidate.head.text and agree_compatible(markable,candidate,lex) or (markable.head.lemma == candidate.head.lemma and
							lex.filters["lemma_match_pos"].match(markable.head.pos) is not None and lex.filters["lemma_match_pos"].match(candidate.head.pos) is not None)):
								if merge_entities(markable, candidate, previous_markables, lex):
									if propagate.startswith("propagate"):
										propagate_entity(markable, candidate, propagate)
									return candidate
							elif entities_compatible(markable, candidate, lex) and (isa(markable, candidate, lex) or isa(candidate, markable, lex)):
									if modifiers_compatible(markable, candidate, lex) and modifiers_compatible(candidate, markable, lex):
										if merge_entities(markable, candidate, previous_markables, lex):
											if propagate.startswith("propagate"):
												propagate_entity(markable, candidate, propagate)
											return candidate
							elif lex.filters["match_acronyms"] and markable.head.text.isupper() or candidate.head.text.isupper():
								if acronym_match(markable, candidate, lex) or acronym_match(candidate, markable, lex):
									if modifiers_compatible(markable, candidate, lex) and modifiers_compatible(candidate, markable, lex):
										if merge_entities(markable, candidate, previous_markables, lex):
											propagate_entity(markable, candidate, "propagate")
											return candidate
							if rule.find("anytext") > -1:
								if (rule.find("anyagree") > -1 and group_agree_compatible(markable,candidate,previous_markables,lex)) or agree_compatible(markable, candidate, lex):
									if propagate.startswith("propagate"):
										propagate_entity(markable, candidate, propagate)
									return candidate
		elif rule.find("lookahead") == -1:
			# Reached back too far according to max_dist, stop looking
			break
			#return None
	if len(candidate_list)>0:
		return best_candidate(markable, candidate_list, lex)
	else:
		return None


def coref_rule_applies(lex, rule, mark, anaphor=None):
	if rule is None or rule == "none":
		return True
	constraints = rule.split("&")
	for constraint in constraints:
		group_failure = False
		negative = False
		if constraint.endswith("*"):
			group_failure = True
			constraint = constraint[0:-1]
		if "=" in constraint:
			key = constraint.split("=")[0]
			value = constraint.split("=")[1]
			if key[-1] == "!":
				negative = True
				key = key[0:-1]
			if value.startswith("/") and value.endswith("/"):
				value = value[1:-1]
			elif value == "True" or value == "False":
				pass
			elif "$" in value and anaphor is not None:
				if key == "form" or key == "text" or key == "agree" or key == "entity" or key == "subclass":
					value = "^" + getattr(anaphor, key).strip() + "$"
				elif key == "text_lower":
					value = "^" + getattr(anaphor, "text").lower() + "$"
				elif key == "cardinality":
					value = "^" + str(getattr(anaphor, "cardinality")) + "$"
				elif key == "func" or key == "pos" or key == "lemma":
					value = "^" + getattr(anaphor.head, key) + "$"
				elif key == "mod":
					mods = getattr(anaphor.head, "modifiers")
					found_mod = False
					for mod1 in mark.head.modifiers:
						for mod2 in mods:
							if mod1.lemma == mod2.lemma and lex.filters["det_func"].match(mod1.func) is None and \
							lex.filters["det_func"].match(mod2.func) is None:
								found_mod = True
					if not found_mod:
						if group_failure and anaphor is not None:
							mark.non_antecdent_groups.add(anaphor.group)
						return False
					else:
						rule_property = "$1"
						key = ""
			if key == "text_lower":
				value = value.lower()
			value_matcher = re.compile(value)
			if key == "form" or key == "text" or key == "agree" or key == "entity" or key == "subclass":
				rule_property = getattr(mark, key).strip()
			elif key == "text_lower":
				rule_property = getattr(mark, "text").lower().strip()
			elif key == "cardinality":
				rule_property = str(getattr(mark, "cardinality"))
			elif key == "func" or key == "pos" or key == "lemma":
				rule_property = getattr(mark.head, key)
			elif key == "quoted":
				rule_property = str(getattr(mark.head, "quoted"))
			elif key == "mood":
				rule_property = mark.sentence.mood
			elif key == "has_child_func":
				rule_property = ""
				for func in mark.head.child_funcs:
					rule_property += func + ";"
			elif key == "head":
				if "$" in value:
					if not mark.head.head == anaphor.head.id:
						if group_failure and anaphor is not None:
							anaphor.non_antecdent_groups.add(mark.group)
						return False
					rule_property = "$1"
				else:
					if re.match(value, mark.head.head) is None:
						if group_failure and anaphor is not None:
							anaphor.non_antecdent_groups.add(mark.group)
						return False
			elif key == "child":
				if "$" in value:
					if not anaphor.head.head == mark.head.id:
						if group_failure and mark is not None:
							mark.non_antecdent_groups.add(anaphor.group)
						return False
					rule_property = "$1"
				else:
					if re.match(value, anaphor.head.head) is None:
						if group_failure and mark is not None:
							mark.non_antecdent_groups.add(anaphor.group)
						return False
			elif re.match(r"last\[([^\[]+)\]", key) is not None:
				match = re.match(r"last\[([^\[]+)\]", key)
				agree = match.group(1)
				if agree in lex.last:
					rule_property = lex.last[agree].entity
				else:
					rule_property = ""
			elif "$" not in rule_property:
				rule_property = ""

			if rule_property is None:
				rule_property = ""

			if (value_matcher.search(rule_property) is None and negative is False) and "$1" not in rule_property:
				if group_failure and anaphor is not None:
					anaphor.non_antecdent_groups.add(mark.group)
				return False
			elif (value_matcher.search(rule_property) is not None and negative is True) and "$1" not in rule_property:
				if group_failure and anaphor is not None:
					anaphor.non_antecdent_groups.add(mark.group)
				return False
		elif constraint == "sameparent":
			if mark.head.head == anaphor.head.head:
				return True
			else:
				if group_failure and anaphor is not None:
					anaphor.non_antecdent_groups.add(mark.group)
				return False
		elif constraint == "!sameparent":
			if mark.head.head == anaphor.head.head:
				if group_failure and anaphor is not None:
					anaphor.non_antecdent_groups.add(mark.group)
				return False
			else:
				return True
	return True


def propagate_entity(markable, candidate, direction="propagate"):
	# Check for rule explicit instructions
	if direction == "propagate_forward":
		markable.entity = candidate.entity
		markable.entity_certainty = "propagated"
		propagate_agree(candidate, markable)
	elif direction == "propagate_back":
		candidate.entity = markable.entity
		candidate.entity_certainty = "propagated"
		propagate_agree(markable, candidate)
	else:
		# Prefer nominal propagates to pronoun
		if markable.form == "pronoun" and candidate.entity_certainty != "uncertain":
			markable.entity = candidate.entity
			propagate_agree(candidate, markable)
			markable.entity_certainty = "propagated"
		elif candidate.form == "pronoun" and markable.entity_certainty != "uncertain":
			candidate.entity = markable.entity
			candidate.entity_certainty = "propagated"
			propagate_agree(markable, candidate)
		else:
			# Prefer certain propagates to uncertain
			if candidate.entity_certainty == "uncertain":
				candidate.entity = markable.entity
				candidate.entity_certainty = "propagated"
				propagate_agree(markable, candidate)
			elif markable.entity_certainty == "uncertain":
				markable.entity = candidate.entity
				markable.entity_certainty = "propagated"
				propagate_agree(candidate, markable)
			else:
				# Prefer to propagate to satisfy alt_entity
				if markable.entity != candidate.entity and markable.entity in candidate.alt_entities:
					candidate.entity = markable.entity
					candidate.entity_certainty = "certain"
					propagate_agree(markable, candidate)
				elif markable.entity != candidate.entity and candidate.entity in markable.alt_entities:
					markable.entity = candidate.entity
					markable.entity_certainty = "certain"
					propagate_agree(candidate, markable)
				else:
					# Prefer to propagate backwards
					candidate.entity = markable.entity
					candidate.entity_certainty = "propagated"
					propagate_agree(markable, candidate)


def propagate_agree(markable, candidate):
	if (candidate.agree == '' or candidate.agree is None) and not (markable.agree == '' or markable.agree is None):
		candidate.agree = markable.agree
	else:
		markable.agree = candidate.agree


def antecedent_prohibited(markable, conll_tokens, lex):
	mismatch = True
	if "/" in lex.filters["no_antecedent"]:
		constraints = lex.filters["no_antecedent"].split(";")
		for constraint in constraints:
			if not mismatch:
				return True
			descriptions = constraint.split("&")
			mismatch = False
			for token_description in descriptions:
				if token_description.startswith("^"):
					test_token = conll_tokens[markable.start]
				elif token_description.startswith("$"):
					test_token = conll_tokens[markable.end]
				elif token_description.startswith("@"):
					test_token = markable.head
				else:
					# Invalid token description
					return False
				token_description = token_description[1:]
				pos, word = token_description.split("/")
				if pos.startswith("!"):
					pos = pos[1:]
					negative_pos = True
				else:
					negative_pos = False
				if word.startswith("!"):
					word = word[1:]
					negative_word = True
				else:
					negative_word = False
				pos_matcher = re.compile(pos)
				word_matcher = re.compile(word)
				if (pos_matcher.match(test_token.pos) is None and not negative_pos) or (pos_matcher.match(test_token.pos) is not None and negative_pos) or \
				(word_matcher.match(test_token.text.strip()) is None and not negative_word) or (word_matcher.match(test_token.text.strip()) is not None and negative_word):
					mismatch = True
					break
	if mismatch:
		return False
	else:
		return True


def acronym_match(mark, candidate, lex):
	position = 0
	calibration = 0
	if mark.head.text.isupper() and len(mark.head.text) > 2:
		for word in candidate.core_text.split(" "):
			if lex.filters["articles"].match(word):
				calibration = -1
			elif len(word) > 0:
				if len(mark.head.text) > position:
					if word[0].isupper() or word == "&":
						if word[0] == mark.head.text[position]:
							position+=1
						else:
							return False
				else:
					return False
		if (position == len(candidate.core_text.strip().split(" ")) + calibration) and position > 2:
			return True
		else:
			return False
	else:
		return False
