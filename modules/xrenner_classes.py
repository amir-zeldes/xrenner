"""
xrenner - eXternally configurable REference and Non Named Entity Recognizer
Basic classes for parsed tokens, markables and sentences.
Author: Amir Zeldes
"""


class ParsedToken:
	def __init__(self, tok_id, text, lemma, pos, morph, head, func, sentence, modifiers, child_funcs, lex, quoted=False):
		self.id = tok_id
		self.text = text
		self.pos = pos
		if lemma != "_" and lemma != "--":
			self.lemma = lemma
		else:
			self.lemma = lex.lemmatize(self)
		self.morph = morph
		if morph != "_" and morph != "--":
			self.morph = lex.process_morph(self)

		self.head = head
		self.func = func
		self.sentence = sentence
		self.modifiers = modifiers
		self.child_funcs = child_funcs
		self.quoted = quoted


class Markable:
	def __init__(self, mark_id, head, form, definiteness, start, end, text, entity, entity_certainty, subclass, infstat, agree, sentence,
				 antecedent, coref_type, group, alt_entities, alt_subclasses, alt_agree):
		self.id = mark_id
		self.head = head
		self.form = form
		self.definiteness = definiteness
		self.start = start
		self.end = end
		self.text = text
		self.core_text = text  # Holds markable text before any extensions or manipulations
		self.entity = entity
		self.subclass = subclass
		self.infstat = infstat
		self.agree = agree
		self.sentence = sentence
		self.antecedent = antecedent
		self.coref_type = coref_type
		self.group = group
		self.non_antecdent_groups = set()
		self.entity_certainty = entity_certainty
		self.isa_partner_head = ""  # Property to hold isa match; once saturated, no other lexeme may form isa link

		#  Alternate agreement, subclass and entity lists:
		self.alt_agree = alt_agree
		self.alt_entities = alt_entities
		self.alt_subclasses = alt_subclasses


class Sentence:
	def __init__(self, sent_num, mood=""):
		self.sent_num = sent_num
		self.mood = mood


def get_descendants(parent, children_dict):
	my_descendants = []
	my_descendants += children_dict[parent]
	for child in children_dict[parent]:
		if child in children_dict:
			my_descendants += get_descendants(child, children_dict)
	return my_descendants
