"""
Basic classes for parsed tokens, markables and sentences.

Author: Amir Zeldes
"""

import sys

class ParsedToken:
	def __init__(self, tok_id, text, lemma, pos, morph, head, func, sentence, modifiers, child_funcs, child_strings, lex, quoted=False, head2="_", func2="_"):
		self.id = tok_id
		self.text = text.strip()
		self.text_lower = text.lower()
		self.pos = pos
		if lemma != "_" and lemma != "--":
			self.lemma = lemma.strip()
		else:
			self.lemma = lex.lemmatize(self)
		self.morph = morph
		if morph != "_" and morph != "--" and morph != "":
			self.morph = lex.process_morph(self)

		self.head = head
		self.original_head = head
		self.func = func
		self.head2 = head2
		self.func2 = func2
		self.sentence = sentence
		self.modifiers = modifiers
		self.child_funcs = child_funcs
		self.child_strings = child_strings
		self.quoted = quoted
		self.coordinate = False
		self.head_text = ""

	def __repr__(self):
		return str(self.text) + " (" + str(self.pos) + "/" + str(self.lemma) + ") " + "<-" + str(self.func) + "- " + str(self.head_text)

class Markable:
	def __init__(self, mark_id, head, form, definiteness, start, end, text, core_text, entity, entity_certainty, subclass, infstat, agree, sentence,
				 antecedent, coref_type, group, alt_entities, alt_subclasses, alt_agree,cardinality=0, submarks=[], coordinate=False):
		self.id = mark_id
		self.head = head
		self.form = form
		self.definiteness = definiteness
		self.start = start
		self.end = end
		self.text = text.strip()
		self.core_text = core_text.strip()  # Holds markable text before any extensions or manipulations
		self.entity = entity
		self.subclass = subclass
		self.infstat = infstat
		self.agree = agree
		self.agree_certainty = ""
		self.sentence = sentence
		self.antecedent = antecedent
		self.coref_type = coref_type
		self.group = group
		self.non_antecdent_groups = set()
		self.entity_certainty = entity_certainty
		self.isa_partner_head = ""  # Property to hold isa match; once saturated, no other lexeme may form isa link

		# Alternate agreement, subclass and entity lists:
		self.alt_agree = alt_agree
		self.alt_entities = alt_entities
		self.alt_subclasses = alt_subclasses

		self.cardinality=cardinality
		self.submarks = submarks
		self.coordinate = coordinate

		self.length = self.text.count(" ") + 1
		self.mod_count = len(self.head.modifiers)

	def has_child_func(self, func):
		if "*" in func: # func substring, do not delimit function
			return func in self.child_func_string
		else: # Exact match, delimit with ";"
			return ";" + func + ";" in self.child_func_string

	def __repr__(self):
		agree = "no-agr" if self.agree == "" else self.agree
		defin = "no-def" if self.definiteness == "" else self.definiteness
		card = "no-card" if self.cardinality == 0 else self.cardinality
		func = "no-func" if self.head.func == "" else self.head.func
		return str(self.entity) + "/" + str(self.subclass) + ': "' + self.text + '" (' + agree + "/" + defin + "/" + func + "/" + str(card) + ")"

	def __getattr__(self, item):
		# Convenience methods to access head token and containing sentence
		if item in ["pos","lemma","morph","parent","func","quoted","modifiers","child_funcs","child_strings","agree"]:
			return getattr(self.head,item)
		elif item == "text_lower":
			if self.coordinate:  # If this is a coordinate markable return lower case core_text
				return self.core_text.lower()
			else:  # Otherwise return lower text of head token
				return getattr(self.head, item)
		elif item in ["mood", "speaker"]:
			return getattr(self.sentence,item)
		elif item == "child_func_string":
			# Check for cached child_func_string
			if "child_func_string" not in self.__dict__:  # Convenience property to store semi-colon separated child funcs of head token
				# Assemble if not yet cached
				if len(self.head.child_funcs) > 1:
					self.child_func_string = ";" + ";".join(self.head.child_funcs) + ";"
				else:
					self.child_func_string = "_"
			return self.child_func_string
		else:
			raise AttributeError


class Sentence:
	def __init__(self, sent_num, start_offset, mood="", speaker=""):
		self.sent_num = sent_num
		self.start_offset = start_offset
		self.mood = mood
		self.speaker = speaker
		self.token_count = 0

	def __repr__(self):
		mood = "(no mood info)" if self.mood == "" else self.mood
		speaker = "(no speaker info)" if self.speaker == "" else self.speaker
		return "S" + str(self.sent_num) + " from T" + str(self.start_offset + 1) + ", mood: " + mood  + ", speaker: " + speaker


def get_descendants(parent, children_dict, seen_tokens, sent_num, conll_tokens):
	my_descendants = []
	my_descendants += children_dict[parent]
	for child in children_dict[parent]:
		if child in seen_tokens:
			sys.stderr.write("\nCycle detected in syntax tree in sentence " + str(sent_num) + " (child of token: '" + conll_tokens[int(parent)].text + "')\n")
			sys.exit("Exiting due to invalid input\n")
		else:
			seen_tokens += [child]
	for child in children_dict[parent]:
		if child in children_dict:
			my_descendants += get_descendants(child, children_dict, seen_tokens, sent_num, conll_tokens)
	return my_descendants
