from collections import defaultdict
from xrenner_marker import *
from xrenner_classes import *
"""
xrenner - eXternally configurable REference and Non Named Entity Recognizer
Coreference resolution module. Iterates through markables to find possible matches based on rules.
Author: Amir Zeldes
"""

def search_prev_markables(markable, previous_markables, rule, lex, max_dist, propagate):
	if rule.find("lookahead") > -1:
		referents_to_loop = previous_markables
	else:
		referents_to_loop = reversed(previous_markables)
	for candidate in referents_to_loop:  # loop through previous markables backwards
		# DEBUG breakpoint: if candidate.text.strip() == "xyz":
		# pass
		if markable.sentence.sent_num - candidate.sentence.sent_num <= max_dist:
			if ((int(markable.head.id) > int(candidate.head.id) and
			rule.find("lookahead") == -1) or (int(markable.head.id) < int(candidate.head.id) and rule.find("lookahead") > -1)):
				if candidate.group not in markable.non_antecdent_groups:
					if coref_rule_applies(lex, rule, candidate, markable):
						if not markables_overlap(markable, candidate):
							if markable.text.strip() == candidate.text.strip():
								propagate_entity(markable, candidate, propagate)
								return candidate
							elif markable.text.strip() + "|" + candidate.text.strip() in lex.coref and entities_compatible(
									markable, candidate, lex) and agree_compatible(markable, candidate, lex):
								markable.coref_type = lex.coref[markable.text.strip() + "|" + candidate.text.strip()]
								propagate_entity(markable, candidate)
								return candidate
							else:
								if markable.form == "pronoun":
									if agree_compatible(markable, candidate, lex) or rule.find("anyagree") > 0:
										if entities_compatible(markable, candidate, lex):
											propagate_entity(markable, candidate)
											return candidate
								elif markable.entity == candidate.entity and (markable.head.text == candidate.head.text or
								(markable.head.lemma == candidate.head.lemma and lex.filters["lemma_match_pos"].match(markable.head.pos) is not None
								and lex.filters["lemma_match_pos"].match(candidate.head.pos) is not None)):
									if not incompatible_modifiers(markable, candidate, lex) and not incompatible_modifiers(candidate, markable, lex):
										if propagate.startswith("propagate"):
											propagate_entity(markable, candidate, propagate)
										return candidate
								elif markable.entity == candidate.entity and (isa(markable, candidate, lex) or isa(candidate, markable, lex)) and agree_compatible(markable, candidate, lex):
									if not incompatible_modifiers(markable, candidate, lex) and not incompatible_modifiers(candidate, markable, lex):
										if propagate.startswith("propagate"):
											propagate_entity(markable, candidate, propagate)
										return candidate
								elif (markable.head.text == candidate.head.text or (markable.head.lemma == candidate.head.lemma and
								lex.filters["lemma_match_pos"].match(markable.head.pos) is not None and lex.filters["lemma_match_pos"].match(candidate.head.pos) is not None)):
									if merge_entities(markable, candidate, previous_markables, lex):
										if propagate.startswith("propagate"):
											propagate_entity(markable, candidate, propagate)
										return candidate
								elif entities_compatible(markable, candidate, lex):
									if isa(markable, candidate, lex) or isa(candidate, markable, lex):
										if not incompatible_modifiers(markable, candidate, lex) and not incompatible_modifiers(candidate, markable, lex):
											if merge_entities(markable, candidate, previous_markables, lex):
												if propagate.startswith("propagate"):
													propagate_entity(markable, candidate, propagate)
												return candidate
								if rule.find("anytext") > -1:
									if rule.find("anyagree") > -1 or agree_compatible(markable, candidate, lex):
										if propagate.startswith("propagate"):
											propagate_entity(markable, candidate, propagate)
										return candidate
		elif rule.find("lookahead") == -1:
			# Reached back too far according to max_dist, stop looking
			return None
	return None


def isa(markable, candidate, lex):
	for subclass in markable.alt_subclasses:
		if subclass in lex.isa:
			if candidate.head.lemma.lower() in lex.isa[subclass] or candidate.text.lower().strip() in lex.isa[subclass]:
				if candidate.isa_partner_head == "" or candidate.isa_partner_head == markable.head.lemma:
					candidate.isa_partner_head = markable.head.lemma
					return True
	if markable.text.strip() in lex.isa:
		if candidate.text.strip() in lex.isa[markable.text.strip()] or candidate.text.strip() in lex.isa[markable.text.strip()]:
			if candidate.isa_partner_head == "" or candidate.isa_partner_head == markable.head.lemma:
				candidate.isa_partner_head = markable.head.lemma
				return True
	# TODO: add prefix/suffix stripped version to catch '*the* United States' = 'America'
	if markable.head.lemma in lex.isa:
		if candidate.head.lemma in lex.isa[markable.head.lemma] or candidate.head.text.strip() in lex.isa[markable.head.lemma]:
			if candidate.isa_partner_head == "" or candidate.isa_partner_head == markable.head.lemma:
				candidate.isa_partner_head = markable.head.lemma
				return True
	return False


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
				if key == "form" or key == "text" or key == "agree" or key == "entity":
					value = "^" + getattr(anaphor, key) + "$"
				elif key == "text_lower":
					value = "^" + getattr(anaphor, "text").lower() + "$"
				elif key == "func" or key == "pos":
					value = "^" + getattr(anaphor.head, key) + "$"
				elif key == "mod":
					mods = getattr(anaphor.head, "modifiers")
					found_mod = False
					for mod1 in mark.head.modifiers:
						for mod2 in mods:
							if mod1.lemma == mod2.lemma:
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
			if key == "form" or key == "text" or key == "agree" or key == "entity":
				rule_property = getattr(mark, key)
			elif key == "text_lower":
				rule_property = getattr(mark, "text").lower()
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

			if (not value_matcher.search(rule_property) and negative is False) and "$" not in rule_property:
				if group_failure and anaphor is not None:
					anaphor.non_antecdent_groups.add(mark.group)
				return False
			elif (value_matcher.search(rule_property) and negative is True) and "$" not in rule_property:
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


def postprocess_coref(markables, lex, markstart, markend, markbyhead):
	# Collect markable groups
	marks_by_group = defaultdict(list)
	for markable in markables:
		marks_by_group[markable.group].append(markable)

	# Order markables in each group to ensure backwards chain
	# except in the case of cataphors, which point forward
	for group in marks_by_group:
		last_mark = None
		for mark in marks_by_group[group]:
			if mark.coref_type != "cata":
				if last_mark is not None:
					mark.antecedent = last_mark
				last_mark = mark

	# Check for markables to remove in postprocessing
	if len(lex.filters["remove_head_func"].pattern) > 0:
		for mark in markables:
			if lex.filters["remove_head_func"].match(mark.head.func) is not None and (mark.form != "proper" or mark.text.strip() == "U.S."): # Proper restriction matches OntoNotes guidelines; US is interpreted as "American" (amod)
				splice_out(mark, marks_by_group[mark.group])
	if len(lex.filters["remove_child_func"].pattern) > 0:
		for mark in markables:
			for child_func in mark.head.child_funcs:
				if lex.filters["remove_child_func"].match(child_func) is not None:
					splice_out(mark, marks_by_group[mark.group])

	# Remove i in i rule (no overlapping markable coreference in group)
	# TODO: make this more efficient (iterates all pairwise comparisons)
	for group in marks_by_group:
		for mark1 in marks_by_group[group]:
			for mark2 in marks_by_group[group]:
				if not mark1 == mark2:
					if markables_overlap(mark1, mark2):
						if (mark1.end - mark1.start) > (mark2.end - mark2.start):
							splice_out(mark2, marks_by_group[group])
						else:
							splice_out(mark1, marks_by_group[group])

	# Inactivate singletons if desired by setting their id to 0
	if lex.filters["remove_singletons"]:
		for group in marks_by_group:
			wipe_group = True
			if len(marks_by_group[group]) < 2:
				for singleton in marks_by_group[group]:
					singleton.id = "0"
			else:
				for singleton_candidate in marks_by_group[group]:
					if singleton_candidate.antecedent is not 'none':
						wipe_group = False
						break
				if wipe_group:
					for singleton in marks_by_group[group]:
						singleton.id = "0"


	# apposition envelope
	env_marks=[]
	for group in marks_by_group:
		#count_env=0
		for i in reversed(range(1,len(marks_by_group[group]))):
			#print marks_by_group[group]
			mark=marks_by_group[group][i]
			prev = mark.antecedent
			if prev != "none":
				if prev.coref_type == "appos" and prev.antecedent != "none":
					#two markables in the envelop:prev and prevprev
					prevprev=prev.antecedent
					envlop=create_envelope(prevprev,prev)
					markables.append(envlop)
					markstart[envlop.start].append(envlop)
					markend[envlop.end].append(envlop)

					#markables_by_head
					head_id=str(prevprev.head.id) + "_" + str(prev.head.id)
					markbyhead[head_id]=envlop

					#set some fields for the envlop markable
					envlop.non_antecdent_groups=prev.antecedent
					#new group number for the two markables inside the envelope
					ab_group=1000+int(prevprev.group)+int(prev.group)
					prevprev.group=ab_group
					prev.group=ab_group
					mark.antecedent=envlop
					prevprev.antecedent="none"
					#count_env+=1
					#break
		#if count_env > 0:
		#	print "this group:" + str(group) + " has created " + str(count_env) + " envelops"
		#	print "====================================="








def splice_out(mark, group):
	min_id = 0
	mark_id = int(mark.id.replace("referent_", ""))
	for member in group:
		if member.antecedent == mark:
			member.antecedent = mark.antecedent
		member_id = int(member.id.replace("referent_", ""))
		if (min_id == 0 or min_id > member_id) and member.id != mark.id:
			min_id = member_id
	mark.antecedent = "none"
	if str(mark_id) != mark.group:
		mark.group = str(mark_id)
	else:
		for member in group:
			if member != mark:
				member.group = str(min_id)
	mark.id = "0"


    
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
				if (pos_matcher.match(test_token.pos) is None and not negative_pos) or (pos_matcher.match(test_token.pos) is not None and negative_pos) and \
				(word_matcher.match(test_token.text.strip()) is None and not negative_word) or (word_matcher.match(test_token.text.strip()) is not None and negative_word):
					mismatch = True
					break
	if mismatch:
		return False
	else:
		return True
    
    
def create_envelope(first,second):
	mark_id="env"
	form = "proper" if (first.form == "proper" or second.form == "proper") else "common"
	head=first.head
	definiteness=first.definiteness
	start=first.start
	end=second.end
	text=first.text.strip() + " " + second.text.strip()
	entity=second.entity
	entity_certainty=second.entity_certainty
	subclass=first.subclass
	infstat=first.infstat
	agree=first.agree
	sentence=first.sentence
	antecedent=first.antecedent
	coref_type=first.coref_type
	group=first.group
	alt_entities=first.alt_entities
	alt_subclasses=first.alt_subclasses
	alt_agree=first.alt_agree



	envelope = Markable(mark_id, head, form, definiteness, start, end, text, entity, entity_certainty, subclass, infstat, agree, sentence, antecedent, coref_type, group, alt_entities, alt_subclasses, alt_agree)

	return envelope