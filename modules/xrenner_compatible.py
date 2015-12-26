import re

"""
xrenner - eXternally configurable REference and Non Named Entity Recognizer
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
	elif mark1.entity is None or mark2.entity is None:
		return True
	if mark1.form == "pronoun" and not (mark1.entity == lex.filters["person_def_entity"] and mark2.entity != lex.filters["person_def_entity"]):
		return True
	if mark1.entity in mark2.alt_entities and mark1.entity != mark2.entity and (mark2.entity_certainty == "uncertain" or mark2.entity_certainty == "propagated"):
		return True
	elif mark2.entity in mark1.alt_entities and mark1.entity != mark2.entity and (mark1.entity_certainty == "uncertain" or mark1.entity_certainty == "propagated"):
		return True

	return False


def modifiers_compatible(markable, candidate, lex):
	"""
	Checks whether the dependents of two markables are compatible for possible coreference
	:param markable: one of two markables to compare dependents for
	:param candidate: the second markable, which is a candidate antecedent for the other markable
	:param lex: the LexData object with gazetteer information and model settings
	:return: bool
	"""

	# Check if markable and candidate have modifiers that are in the antonym list together,
	# e.g. 'the good news' should not be coreferent with 'the bad news'
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

	# Check if markable and candidate have modifiers that are different place names
	# e.g. 'Georgetown University' is incompatible with 'Boston University' even if those entities are not in lexicon
	for mod in markable.head.modifiers:
		if mod.text.strip() in lex.entities and (mod.text.istitle() or not lex.filters["cap_names"]):
			if re.sub('\t.*', "", lex.entities[mod.text.strip()][0]) == lex.filters["place_def_entity"]:
				for candidate_mod in candidate.head.modifiers:
					if candidate_mod.text.strip() in lex.entities and (candidate_mod.text.istitle() or not lex.filters["cap_names"]):
						if re.sub('\t.*', "", lex.entities[candidate_mod.text.strip()][0]) == lex.filters["place_def_entity"]:
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

	# Recursive check through antecedent ancestors in group
	if candidate.antecedent != "none":
		antecdent_compatible = modifiers_compatible(markable, candidate.antecedent, lex)
		if antecdent_compatible:
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
	Negotiates entity mismtaches across coreferent markables and their groups.
	Returns True if merging has occured.
	:param mark1: the first of two markables to merge entities for
	:param mark2: the second of two markables to merge entities for
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
	Checks whether two markables are compatible for coreference via the isa-relation
	:param markable: one of two markables to compare lexical isa relationship with
	:param candidate: the second markable, which is a candidate antecedent for the other markable
	:param lex: the LexData object with gazetteer information and model settings
	:return: bool
	"""

	if not lex.filters["allow_indef_anaphor"]:
		# Don't allow an indefinite to have a definite antecedent via isa relation
		if markable.start > candidate.start:
			if markable.definiteness == "indef" and candidate.definiteness =="def":
				return False
		else:
			if markable.definiteness == "def" and candidate.definiteness =="indef":
				return False

		# Don't allow a proper markable to have an indefinite antecedent via isa relation
		if markable.start > candidate.start:
			if markable.form == "proper" and candidate.definiteness == "indef":
				return False
		else:
			if markable.definiteness == "indef" and candidate.form =="proper":
				return False


	# Subclass based isa match - check agreement too
	for subclass in markable.alt_subclasses:
		if subclass in lex.isa:
			if candidate.head.lemma.lower() in lex.isa[subclass] or candidate.text.lower().strip() in lex.isa[subclass]:
				if candidate.isa_partner_head == "" or candidate.isa_partner_head == markable.head.lemma:
					if agree_compatible(markable, candidate, lex):
						candidate.isa_partner_head = markable.head.lemma
						return True

	# Exact text match in isa table - no agreement matching is carried out
	if markable.text.strip() in lex.isa:
		if candidate.text.strip() in lex.isa[markable.text.strip()] or candidate.text.strip() in lex.isa[markable.text.strip()]:
			if candidate.isa_partner_head == "" or candidate.isa_partner_head == markable.head.lemma:
				candidate.isa_partner_head = markable.head.lemma
				return True
	# TODO: add prefix/suffix stripped version to catch '*the* United States' = 'America'

	# Head isa match - no agreement matching is carried out
	if markable.head.text.strip() in lex.isa:
		if candidate.head.text.strip() in lex.isa[markable.head.text.strip()] or candidate.head.text.strip() in lex.isa[markable.head.text.strip()]:
			if candidate.isa_partner_head == "" or candidate.isa_partner_head == markable.head.lemma:
				candidate.isa_partner_head = markable.head.lemma
				return True

	# Lemma based isa matching - check agreement too
	if markable.head.lemma in lex.isa:
		if candidate.head.lemma in lex.isa[markable.head.lemma] or candidate.head.text.strip() in lex.isa[markable.head.lemma]:
			if candidate.isa_partner_head == "" or candidate.isa_partner_head == markable.head.lemma:
				if agree_compatible(markable, candidate, lex):
					candidate.isa_partner_head = markable.head.lemma
					return True
	return False
