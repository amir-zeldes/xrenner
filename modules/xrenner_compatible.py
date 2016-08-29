import re
from xrenner_marker import remove_suffix_tokens
from xrenner_propagate import *
from xrenner_classes import Markable
from math import log

"""
Module for checking compatibility of various features between markables

Author: Amir Zeldes
"""


def entities_compatible(mark1, mark2, lex):
	"""
	Checks if the entity property of two markables is compatible for possible coreference
	
	:param mark1: the first of two markables to compare entities
	:param mark2: the second of two markables to compare entities
	:param lex: the LexData object with gazetteer information and model settings
	:return: bool
	"""

	if mark1.entity == mark2.entity:
		return True
	elif mark1.entity is None or mark2.entity is None or mark1.entity == "" or mark2.entity == "":
		return True
	if mark1.form == "pronoun" and (not (mark1.entity == lex.filters["person_def_entity"] and mark2.entity != lex.filters["person_def_entity"]) or mark1.entity_certainty == ''):
		return True
	if mark1.entity != mark2.entity:
		if mark1.entity in mark2.alt_entities and (mark2.entity_certainty == "uncertain" or mark2.entity_certainty == "propagated"):
			return True
		elif mark2.entity in mark1.alt_entities and (mark1.entity_certainty == "uncertain" or mark1.entity_certainty == "propagated"):
			return True
		elif mark2.entity == lex.filters["default_entity"] and mark2.entity_certainty in ["","propagated","uncertain"]:
			return True
		elif mark1.entity == lex.filters["default_entity"] and mark1.entity_certainty in ["","propagated","uncertain"]:
			return True

	return False


def cardinality_compatible(mark1,mark2,lex):
	if "ablations" in lex.debug:
		if "no_cardinality" in lex.debug["ablations"]:
			return True
	if mark1.cardinality!=0:
		if mark2.cardinality!=0:
			if mark1.cardinality != mark2.cardinality:
				return False
	return True


def modifiers_compatible(markable, candidate, lex, allow_force_proper_mod_match=True):
	"""
	Checks whether the dependents of two markables are compatible for possible coreference
	
	:param markable: one of two markables to compare dependents for
	:param candidate: the second markable, which is a candidate antecedent for the other markable
	:param lex: the LexData object with gazetteer information and model settings
	:return: bool
	"""

	if markable.id+"|"+candidate.id in lex.incompatible_mod_pairs:
		return False

	if allow_force_proper_mod_match:
		proper_mod_must_match = lex.filters["proper_mod_must_match"]
	else:
		proper_mod_must_match = False

	if not cardinality_compatible(markable,candidate,lex):
		return False

	# Do strict 'no new modifiers' check if desired
	if lex.filters["no_new_modifiers"]:
		if markable.start > candidate.start:
			first = candidate
			second = markable
		else:
			first = markable
			second = candidate
		first_mods = (comp_mod.text for comp_mod in first.head.modifiers)
		for mod in second.head.modifiers:
			if lex.filters["det_func"].match(mod.func) is None:  # Exclude determiners from this check
				if mod.text not in first_mods:
					if lex.filters["use_new_modifier_exceptions"]:
						if mod.text not in lex.exceptional_new_modifiers:
							return False
					else:
						return False

	# Check if markable and candidate have modifiers that are in the antonym list together,
	# e.g. 'the good news' should not be coreferent with 'the bad news',
	antonym_check = True
	if "ablations" in lex.debug:
		if "no_antonyms" in lex.debug["ablations"]:
			antonym_check = False
	if antonym_check:
		for mod in markable.head.modifiers:
			if mod.text.lower() in lex.antonyms:
				for candidate_mod in candidate.head.modifiers:
					if candidate_mod.text.lower() in lex.antonyms[mod.text.lower()]:
						markable.non_antecdent_groups.add(candidate.group)
						return False
			elif mod.lemma.lower() in lex.antonyms:
				for candidate_mod in candidate.head.modifiers:
					if candidate_mod.lemma.lower() in lex.antonyms[mod.lemma.lower()]:
						markable.non_antecdent_groups.add(candidate.group)
						return False
			# Check that the two markables do not have non-identical proper noun modifiers
			if proper_mod_must_match:
				if lex.filters["proper_pos"].match(mod.pos):
					candidate_proper_mod_texts = []
					for mod2 in candidate.head.modifiers:
						if lex.filters["proper_pos"].match(mod2.pos):
							candidate_proper_mod_texts.append(mod2.text)
					if mod.text not in candidate_proper_mod_texts and len(candidate_proper_mod_texts) > 0:
						return False

	# Check if markable and candidate have modifiers that are different place names
	# e.g. 'Georgetown University' is incompatible with 'Boston University' even if those entities are not in lexicon
	for mod in markable.head.modifiers:
		if mod.text in lex.entities and (mod.text.istitle() or not lex.filters["cap_names"]):
			if re.sub('\t.*', "", lex.entities[mod.text][0]) == lex.filters["place_def_entity"]:
				for candidate_mod in candidate.head.modifiers:
					if candidate_mod.text != mod.text:
						if candidate_mod.text in lex.entities and (candidate_mod.text.istitle() or not lex.filters["cap_names"]):
							if re.sub('\t.*', "", lex.entities[candidate_mod.text][0]) == lex.filters["place_def_entity"]:
								markable.non_antecdent_groups.add(candidate.group)
								return False

	# Check for each possible pair of modifiers with identical function in the ident_mod list whether they are identical,
	# e.g. for the num function 'the four children' shouldn't be coreferent with 'five other children'
	for mod in markable.head.modifiers:
		for candidate_mod in candidate.head.modifiers:
			# TODO: add support for ident_mod pos func combo:
			# if lex.filters["ident_mod_func"].match(mod.func+"+"+mod.pos) and lex.filters["ident_mod_func"].match(candidate_mod.func+"+"+candidate_mod.pos) and
			# mod.text.lower != candidate_mod.text.lower():
			if lex.filters["ident_mod_func"].match(mod.func) is not None and lex.filters["ident_mod_func"].match(candidate_mod.func) is not None and mod.text.lower != candidate_mod.text.lower():
				markable.non_antecdent_groups.add(candidate.group)
				return False

	# Check that heads are not antonyms themselves
	if markable.head.lemma in lex.antonyms:
		if candidate.head.lemma in lex.antonyms[markable.head.lemma]:
			return False
		if candidate.head.lemma.isupper() and candidate.head.lemma.lower() in lex.antonyms[markable.head.lemma]:
			return False

	# Check that the heads are not conflicting proper names
	if markable.form == "proper" and candidate.form == "proper":
		if markable.text != candidate.text:
			if markable.text in lex.names and candidate.text in lex.names:
				return False
			elif markable.text.count(" ") == 0 and candidate.text.count(" ") == 0:
				isa = False
				if markable.text in lex.first_names and candidate.text in lex.first_names:
					if markable.text in lex.isa:
						if candidate.text.lower() in lex.isa[markable.text]:
							isa = True
					if candidate.text in lex.isa:
						if markable.text.lower() in lex.isa[candidate.text]:
							isa = True
					if not isa:
						return False
				if markable.text in lex.last_names and candidate.text in lex.last_names:
					if markable.text in lex.isa:
						if candidate.text.lower() in lex.isa[markable.text]:
							isa = True
					if candidate.text in lex.isa:
						if markable.text.lower() in lex.isa[candidate.text]:
							isa = True
					if not isa:
						return False

	# Recursive check through antecedent ancestors in group
	if isinstance(candidate.antecedent, Markable):
		antecedent_compatible = modifiers_compatible(markable, candidate.antecedent, lex)
		if not antecedent_compatible:
			return False

	return True


def agree_compatible(mark1, mark2, lex):
	"""
	Checks if the agree property of two markables is compatible for possible coreference
	
	:param mark1: the first of two markables to compare agreement
	:param mark2: the second of two markables to compare agreement
	:param lex: the LexData object with gazetteer information and model settings
	:return: bool
	"""

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


def merge_entities(mark1, mark2, previous_markables, lex):
	"""
	Negotiates entity mismatches across coreferent markables and their groups.
	Returns True if merging has occurred.
	
	:param mark1: the first of two markables to merge entities for
	:param mark2: the second of two markables to merge entities for
	:param previous_markables: all previous markables which may need to inherit from the model/host
	:param lex: the LexData object with gazetteer information and model settings
	:return: bool
	"""

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
	"""
	Attempts to update entire coreference group of a host markable with information
	gathered from a model markable discovered to be possibly coreferent with the host.
	If incompatible modifiers are discovered the process fails and returns False.
	Otherwise updating succeeds and the update_group returns true
	
	:param host: the first markable discovered to be coreferent with the model
	:param model: the model markable, containing new information for the group
	:param previous_markables: all previous markables which may need to inherit from the model/host
	:param lex: the LexData object with gazetteer information and model settings
	:return: bool
	"""

	group = host.group
	for markable in previous_markables:
		if markable.group == group:
			if not modifiers_compatible(markable, model, lex):
				return False
	for markable in previous_markables:
		if markable.group == group:
			markable.entity = model.entity
			markable.subclass = model.subclass
	return True

def isa(markable, candidate, lex):
	"""
	Staging function to check for and store new cached isa information.
	Calls actual :func:`run_isa` function if pair is still viable for new isa match.

	:param markable: one of two markables to compare lexical isa relationship with
	:param candidate: the second markable, which is a candidate antecedent for the other markable
	:param lex: the LexData object with gazetteer information and model settings
	:return: bool
	"""

	retval = False
	if markable.id+"|"+candidate.id not in lex.incompatible_isa_pairs:
		retval = run_isa(markable, candidate, lex)
		if not retval:
			lex.incompatible_isa_pairs.add(markable.id+"|"+candidate.id)
	return retval

def run_isa(markable, candidate, lex):
	"""
	Checks whether two markables are compatible for coreference via the isa-relation

	:param markable: one of two markables to compare lexical isa relationship with
	:param candidate: the second markable, which is a candidate antecedent for the other markable
	:param lex: the LexData object with gazetteer information and model settings
	:return: bool
	"""

	if "ablations" in lex.debug:
		if "no_isa" in lex.debug["ablations"]:
			return False

	if not lex.filters["allow_indef_anaphor"]:
		# Don't allow an indefinite to have a definite antecedent via isa relation
		if markable.start > candidate.start:
			if markable.definiteness == "indef" and candidate.definiteness =="def":
				return False
		else:
			if markable.definiteness == "def" and candidate.definiteness =="indef":
				return False

		# Don't allow a proper markable to have an indefinite antecedent via isa relation
		# unless there's corroborating evidence
		#if markable.cardinality == candidate.cardinality and markable.cardinality != 0:
		#	pass  # Explicit cardinality match, forgo indefinite antecedent prohibition
		#elif markable.subclass == candidate.subclass and markable.agree == candidate.agree:
		#	pass  # Explicit subclass and agree match, forgo indefinite antecedent prohibition
		#else: TODO: re-examine indefinite isa antecedents in natural data
		if markable.start > candidate.start:
			if markable.form == "proper" and candidate.definiteness == "indef":
				return False
		else:
			if markable.definiteness == "indef" and candidate.form == "proper":
				return False

	if not lex.filters["allow_indef_isa"]:
		# Don't allow an indefinite to have any antecedent via isa relation if forbidden by configuration
		if markable.start > candidate.start:
			if markable.definiteness == "indef":
				return False
		else:
			if candidate.definiteness =="indef":
				return False

	# Check for incompatible modifiers
	if len(markable.modifiers) > 0:
		if not modifiers_compatible(markable,candidate, lex):
			lex.incompatible_mod_pairs.add(markable.id+"|"+candidate.id)
			return False

	# Check for first name + full name match
	if markable.entity in ["", lex.filters["person_def_entity"]] and candidate.entity in ["", lex.filters["person_def_entity"]]:
		if markable.head.text in lex.first_names:
			candidate_mod_texts = list((mod.text) for mod in candidate.head.modifiers)
			if markable.head.text in candidate_mod_texts:
				return True
		if candidate.head.text in lex.first_names:
			markable_mod_texts = list((mod.text) for mod in markable.head.modifiers)
			if candidate.head.text in markable_mod_texts:
				return True

	# Forbid isa head matching for two distinct proper names except first+full name; NB: use coref table for these if desired
	if markable.form == "proper" and candidate.form == "proper":
		if markable.text in lex.names or markable.text in lex.first_names:
			if candidate.text in lex.names or candidate.text in lex.first_names:
				#return False
				pass

	# Subclass based isa match - check agreement too unless disabled
	# Note that this check is unidirectional: the subclass can match an antecedent instance of it,
	# but prior mention of the subclass is not matched to a subsequent instance
	# (the Guardian .. < .. the newspaper is OK, but not: the newspaper .. < .. the Guardian)
	for subclass in candidate.alt_subclasses + [candidate.subclass]:
		if subclass == markable.lemma:
			if agree_compatible(markable, candidate, lex) and not never_agree(markable, candidate, lex):
				# Check if this case is already assigned a different lexical head as isa partner
				if markable.isa_partner_head == "" or markable.isa_partner_head == candidate.lemma:
					markable.isa_partner_head = candidate.lemma
					return True
				else:  # Another lemma is already isa-linked to this, e.g. state <- Oregon; so now not also "Nevada"
					return False
		if subclass in lex.isa:
			if lex.isa[subclass][-1] == "*":
				subclass_isa = lex.isa[subclass][:-1]
				check_agree = False
			else:
				subclass_isa = lex.isa[subclass]
				check_agree = lex.filters["isa_subclass_agreement"]
			if markable.lemma.lower() in subclass_isa:
				if markable.isa_partner_head == "" or markable.isa_partner_head == candidate.lemma or candidate.isa_partner_head == markable.lemma:
					if (agree_compatible(markable, candidate, lex) or check_agree is False) and not never_agree(markable, candidate, lex):
						markable.isa_partner_head = candidate.lemma
						return True

	# Exact text match in isa table - no agreement matching is carried out
	if markable.text in lex.isa:
		if candidate.text in lex.isa[markable.text]:
			if candidate.isa_partner_head == "" or candidate.isa_partner_head == markable.head.lemma:
				candidate.isa_partner_head = markable.head.lemma
				return True
	if candidate.text in lex.isa:
		if markable.text in lex.isa[candidate.text]:
			if markable.isa_partner_head == "" or markable.isa_partner_head == candidate.head.lemma:
				markable.isa_partner_head = candidate.head.lemma
				return True

	# Core text isa match
	# Note this check is unidirectional
	if markable.core_text in lex.isa:
		if candidate.core_text in lex.isa[markable.core_text] or candidate.head.lemma in lex.isa[markable.core_text]:
			if candidate.isa_partner_head == "" or candidate.isa_partner_head == markable.head.lemma:
				if agree_compatible(markable, candidate, lex) and not never_agree(markable, candidate, lex):
					candidate.isa_partner_head = markable.head.lemma
					return True
		# Head-core text isa match - no agreement matching is carried out
		elif candidate.head.text in lex.isa[markable.core_text]:
			if candidate.isa_partner_head == "" or candidate.isa_partner_head == markable.head.lemma:
				candidate.isa_partner_head = markable.head.lemma
				return True
	elif markable.core_text.isupper():  # Try to title case on all caps entity
		if markable.core_text.title() in lex.isa:
			if candidate.core_text in lex.isa[markable.core_text.title()] or candidate.head.lemma in lex.isa[markable.core_text.title()]:
				if candidate.isa_partner_head == "" or candidate.isa_partner_head == markable.head.lemma:
					candidate.isa_partner_head = markable.head.lemma
					return True

	# Handle cases where a prefix like an article is part of the entity name, but a suffix like a possessive isn't
	if remove_suffix_tokens(markable.text,lex) in lex.isa:
		if candidate.head.text in lex.isa[remove_suffix_tokens(markable.text,lex)]:
			if candidate.isa_partner_head == "" or candidate.isa_partner_head == markable.head.lemma:
				candidate.isa_partner_head = markable.head.lemma
				return True
	elif remove_suffix_tokens(candidate.text, lex) in lex.isa:
		if markable.head.text in lex.isa[remove_suffix_tokens(candidate.text, lex)]:
			if markable.isa_partner_head == "" or markable.isa_partner_head == candidate.head.lemma:
				markable.isa_partner_head = candidate.head.lemma
				return True

	# Head-head isa match - no agreement matching is carried out
	if markable.head.text in lex.isa:
		if candidate.head.text in lex.isa[markable.head.text]:
			if candidate.isa_partner_head == "" or candidate.isa_partner_head == markable.head.lemma:
				candidate.isa_partner_head = markable.head.lemma
				return True
	if candidate.head.text in lex.isa:
		if markable.head.text in lex.isa[candidate.head.text]:
			if markable.isa_partner_head == "" or markable.isa_partner_head == candidate.head.lemma:
				markable.isa_partner_head = candidate.head.lemma
				return True

	# Lemma based isa matching - check agreement too
	if markable.head.lemma in lex.isa:
		if candidate.head.lemma in lex.isa[markable.head.lemma] or candidate.head.text in lex.isa[markable.head.lemma]:
			if candidate.isa_partner_head == "" or candidate.isa_partner_head == markable.head.lemma:
				if agree_compatible(markable, candidate, lex):
					candidate.isa_partner_head = markable.head.lemma
					return True
	if candidate.head.lemma in lex.isa:
		if markable.head.lemma in lex.isa[candidate.head.lemma] or markable.head.text in lex.isa[candidate.head.lemma]:
			if markable.isa_partner_head == "" or markable.isa_partner_head == candidate.head.lemma:
				if agree_compatible(markable, candidate, lex):
					markable.isa_partner_head = candidate.head.lemma
					return True

	return False


def group_agree_compatible(markable,candidate,previous_markables,lex):
	"""
	:param markable: markable whose group the candidate might be joined to
	:param candidate: candidate to check for compatibility with all group members
	:param previous_markables: all previous markables which may need to inherit from the model/host
	:param lex: the LexData object with gazetteer information and model settings
	:return: bool
	"""
	if "+" in lex.filters["never_agree_pairs"]:
		never_agreement_pairs = lex.filters["never_agree_pairs"].split(";")
		agreements = []
		for mark in previous_markables:
			if mark.group == markable.group or mark.group == candidate.group:
				agreements.append(mark.agree)

		for pair in never_agreement_pairs:
			class1, class2 = pair.split("+")
			if class1 in agreements and class2 in agreements:
				return False
	return True


def never_agree(candidate, markable, lex):
	if "+" in lex.filters["never_agree_pairs"]:
		never_agreement_list = lex.filters["never_agree_pairs"].split(";")
		never_agreement_pairs = []
		for pair in never_agreement_list:
			never_agreement_pairs.append(pair.split("+"))
		if [markable.agree, candidate.agree] in never_agreement_pairs or [candidate.agree, markable.agree] in never_agreement_pairs:
			return True
	return False


def best_candidate(markable,candidate_list,lex, propagate):
	"""
	:param markable: markable to find best antecedent for
	:param candidate_list: list of markables which are possible antecedents based on some coref_rule
	:param lex: the LexData object with gazetteer information and model settings
	:return: Markable object or None (the selected best antecedent markable, if available)
	"""
	anaphor_parent = markable.head.head_text
	candidate_scores = {}
	entity_dep_scores = {}
	best = None

	use_entity_deps = True
	if "ablations" in lex.debug:
		if "no_entity_dep" in lex.debug["ablations"]:
			use_entity_deps = False
	use_hasa = True
	if "ablations" in lex.debug:
		if "no_hasa" in lex.debug["ablations"]:
			use_hasa = False

	if anaphor_parent in lex.entity_deps and use_entity_deps:
		if markable.head.func in lex.entity_deps[anaphor_parent]:
			for entity in lex.entity_deps[anaphor_parent][markable.head.func]:
				entity_dep_scores[entity] = lex.entity_deps[anaphor_parent][markable.head.func][entity]
	
	for candidate in candidate_list:
		candidate_scores[candidate] = 0 - (markable.sentence.sent_num - candidate.sentence.sent_num)
		candidate_scores[candidate] -= ((markable.start - candidate.end) * 0.00001 + (markable.start - candidate.start) * 0.000001) # Break ties via proximity
		if candidate.entity in entity_dep_scores:
			candidate_scores[candidate] += log(entity_dep_scores[candidate.entity]+1)
		if candidate.entity == lex.filters["person_def_entity"]:  # Introduce slight bias to persons
			candidate_scores[candidate] += 0.1
		if candidate.entity == lex.filters["subject_func"]:  # Introduce slight bias to subjects
			candidate_scores[candidate] += 0.95
		if candidate.agree == markable.agree:  # Slight bias to explicitly identical agreement (not just compatible)
			candidate_scores[candidate] += 0.1
		if candidate.head.text in lex.hasa and use_hasa and lex.filters["possessive_func"].search(markable.head.func) is not None:  # Text based hasa
			if anaphor_parent in lex.hasa[candidate.head.text]:
				candidate_scores[candidate] += log(lex.hasa[candidate.head.text][anaphor_parent]+1) * 1.1
		elif candidate.head.lemma in lex.hasa and use_hasa and lex.filters["possessive_func"].search(markable.head.func) is not None:  # Lemma based hasa
			if anaphor_parent in lex.hasa[candidate.head.lemma]:
				candidate_scores[candidate] += log(lex.hasa[candidate.head.lemma][anaphor_parent]+1) * 0.9

	max_score = ''
	for candidate in candidate_scores:
		if max_score == '':
			max_score = candidate_scores[candidate]
			best = candidate
		elif candidate_scores[candidate] > max_score:
			max_score = candidate_scores[candidate]
			best = candidate

	#if propagate.startswith("propagate"):
	#	propagate_entity(markable,best,propagate)
	markable.entity = best.entity
	#markable.agree = best.agree
	markable.entity_certainty = "propagated"
	propagate_agree(markable, best)
	return best


def stems_compatible(verb, noun, lex):
	verb_stem = lex.filters["stemmer_deletes"].sub("",verb.text)
	noun_stem = lex.filters["stemmer_deletes"].sub("",noun.text)
	if verb_stem == noun_stem and len(noun_stem)>3:
		return True
	return False


def acronym_match(mark, candidate, lex):
	"""
	Check whether a Markable's text is an acronym of a candidate Markable's text
	
	:param mark: The Markable object to test
	:param candidate: The candidate Markable with potentially acronym-matching text
	:param lex: the LexData object with gazetteer information and model settings
	:return: bool
	"""
	position = 0
	calibration = 0
	candidate_string = candidate.core_text
	if "ignore_in_acronym" in lex.filters:
		candidate_string = lex.filters["ignore_in_acronym"].sub("", candidate_string)
		candidate_string = candidate_string.replace("  "," ")

	if mark.head.text.isupper() and len(mark.head.text) > 2:
		for word in candidate_string.split(" "):
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
		if (position == len(candidate_string.strip().split(" ")) + calibration) and position > 2:
			return True
		else:
			return False
	else:
		return False
