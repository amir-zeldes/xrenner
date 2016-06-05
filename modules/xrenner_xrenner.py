#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Main class file for Xrenner() class

Author: Amir Zeldes
"""

from collections import OrderedDict
from xrenner_out import *
from xrenner_classes import *
from xrenner_coref import *
from xrenner_preprocess import *
from xrenner_marker import make_markable
from xrenner_lex import *
from xrenner_postprocess import postprocess_coref
from depedit import run_depedit
import ntpath, os


class Xrenner:

	def __init__(self, model="eng", override=None):
		"""
		Main class for xrenner coreferencer
		
		:param model:  model directory in models/ specifying settings and gazetteers for this language (default: eng)
		:param override: name of a section in models/override.ini if configuration overrides should be applied
		:return: void
		"""

		self.model = model
		self.override = override
		self.lex = LexData(self.model, self.override)

	def analyze(self, infile, out_format):
		"""
		Method to run coreference analysis with loaded model
		
		:param infile: file name of the parse file in the conll10 format, or the pre-read parse itself
		:param format: format to determine output type, one of: html, paula, webanno, conll, onto, unittest
		:return: output based on requested format
		"""

		# Check if this is a file name from the main script or a parse delivered in an import or unittest scenario
		if "\t" in infile or isinstance(infile,list):  # This is a raw parse as string or list, not a file name
			self.docpath = os.path.dirname(os.path.abspath("."))
			self.docname = "untitled"
		else:  # This is a file name, extract document name and path, then read the file
			self.docpath = os.path.dirname(os.path.abspath(infile))
			self.docname = clean_filename(ntpath.basename(infile))
			infile = open(infile)

		depedit_config = open(os.path.dirname(os.path.realpath(__file__)) + os.sep + ".." + os.sep + "models" + os.sep + self.model + os.sep + "depedit.ini")

		infile = run_depedit(infile, depedit_config)
		infile = infile.split("\n")

		# Lists and dictionaries to hold tokens and markables
		self.conll_tokens = []
		self.conll_tokens.append(ParsedToken(0, "ROOT", "--", "XX", "", -1, "NONE", Sentence(1, 0, ""), [], [], [], self.lex))
		self.markables = []
		self.markables_by_head = OrderedDict()
		self.markstart_dict = defaultdict(list)
		self.markend_dict = defaultdict(list)

		self.tokoffset = 0
		self.sentlength = 0
		self.markcounter = 1
		self.groupcounter = 1

		self.children = defaultdict(list)
		self.descendants = {}
		self.child_funcs = defaultdict(list)
		self.child_strings = defaultdict(list)

		# Dereference object classes to method globals for convenience
		lex = self.lex
		conll_tokens = self.conll_tokens
		markstart_dict = self.markstart_dict
		markend_dict = self.markend_dict


		self.sent_num = 1
		quoted = False
		current_sentence = Sentence(self.sent_num, self.tokoffset, "")

		for myline in infile:
			if "#speaker" in myline: # speaker
				current_sentence.speaker = myline.split('"')[1]
			elif myline.find("\t") > 0:  # Only process lines that contain tabs (i.e. conll tokens)
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
				head_id = "0" if cols[6] == "0" else str(int(cols[6]) + self.tokoffset)
				conll_tokens.append(ParsedToken(str(int(cols[0]) + self.tokoffset), cols[1], cols[2], cols[3], cols[5],
												head_id, tok_func, current_sentence, [], [], [], lex, quoted))
				self.sentlength += 1
				# Check not to add a child if this is a function which discontinues the markable span
				if not (lex.filters["non_link_func"].match(tok_func) is not None or lex.filters["non_link_tok"].match(cols[1]) is not None):
					if cols[6] != "0":  # Do not add children to the 'zero' token
						self.children[str(int(cols[6]) + self.tokoffset)].append(str(int(cols[0]) + self.tokoffset))
				self.child_funcs[(int(cols[6]) + self.tokoffset)].append(tok_func)
				self.child_strings[(int(cols[6]) + self.tokoffset)].append(cols[1])
			elif self.sentlength > 0:
				self.process_sentence(self.tokoffset, current_sentence)
				self.sent_num += 1
				if self.sentlength > 0:
					self.tokoffset += self.sentlength
				current_sentence = Sentence(self.sent_num, self.tokoffset, "")

				self.sentlength = 0

		# Handle leftover sentence which did not have trailing newline
		if self.sentlength > 0:
			self.process_sentence(self.tokoffset, current_sentence)

		marks_to_add = []
		if lex.filters["seek_verb_for_defs"]:
			for mark in self.markables:
				if mark.definiteness == "def" and mark.antecedent == "none" and mark.form == "common" and \
				(lex.filters["event_def_entity"] == mark.entity or lex.filters["abstract_def_entity"] == mark.entity):
					for tok in conll_tokens[0:mark.start]:
						if lex.filters["verb_head_pos"].match(tok.pos):
							if stems_compatible(tok,mark.head,lex):
								v_antecedent = make_markable(tok,conll_tokens,{},tok.sentence.start_offset,tok.sentence,[],lex)
								mark.antecedent = v_antecedent
								mark.coref_type = "coref"
								v_antecedent.entity = mark.entity
								v_antecedent.subclass = mark.subclass
								v_antecedent.definiteness = "none"
								v_antecedent.form = "verbal"
								v_antecedent.infstat = "new"
								v_antecedent.group = mark.group
								v_antecedent.id = "referent_" + v_antecedent.head.id
								marks_to_add.append(v_antecedent)


		for mark in marks_to_add:
			markstart_dict[mark.start].append(mark)
			markend_dict[mark.end].append(mark)
			self.markables_by_head[mark.head.id] = mark
			self.markables.append(mark)


		postprocess_coref(self.markables, lex, markstart_dict, markend_dict, self.markables_by_head, conll_tokens)

		if out_format == "paula":
			try:
				self.serialize_output(out_format)
				return True
			except:
				return False
		else:
			return self.serialize_output(out_format, infile)

	def serialize_output(self, out_format, parse=None):
		"""
		Return a string representation of the output in some format, or generate PAULA directory structure as output
		
		:param out_format: the format to generate, one of: html, paula, webanno, conll, onto, unittest
		:param parse: the original parse input fed to xrenner; only needed for unittest output
		:return: specified output format string, or void for paula
		"""
		conll_tokens = self.conll_tokens
		markables, markstart_dict, markend_dict = self.markables, self.markstart_dict, self.markend_dict

		if out_format == "html":
			rtl = True if self.model in ["heb","ara"] else False
			return output_HTML(conll_tokens, markstart_dict, markend_dict, rtl)
		elif out_format == "paula":
			output_PAULA(conll_tokens, markstart_dict, markend_dict, self.docname, self.docpath)
		elif out_format == "webanno":
			return output_webanno(conll_tokens[1:], markables)
		elif out_format == "conll":
			return output_conll(conll_tokens, markstart_dict, markend_dict, self.docname, True)
		elif out_format == "onto":
			return output_onto(conll_tokens, markstart_dict, markend_dict, self.docname)
		elif out_format == "unittest":
			from xrenner_test import generate_test
			return generate_test(conll_tokens, markables, parse, self.model)
		else:
			return output_SGML(conll_tokens, markstart_dict, markend_dict)

	def process_sentence(self, tokoffset, sentence):
		"""
		Function to analyze a single sentence
		
		:param tokoffset: the offset in tokens for the beginning of the current sentence within all input tokens
		:param sentence: the Sentence object containin mood, speaker and other information about this sentence
		:return: void
		"""
		markables = self.markables
		markables_by_head = self.markables_by_head

		lex = self.lex
		conll_tokens = self.conll_tokens
		child_funcs = self.child_funcs
		child_strings = self.child_strings
		children = self.children
		descendants = self.descendants
		markstart_dict = self.markstart_dict
		markend_dict = self.markend_dict

		# Add list of all dependent funcs and strings to each token
		add_child_info(conll_tokens, child_funcs, child_strings)

		mark_candidates_by_head = OrderedDict()
		stop_ids = {}
		for tok1 in conll_tokens[tokoffset + 1:]:
			stop_ids[tok1.id] = False  # Assume all tokens are head candidates

		# Post-process parser input based on entity list if desired
		if lex.filters["postprocess_parser"]:
			postprocess_parser(conll_tokens, tokoffset, children, stop_ids, lex)

		# Revert conj token function to parent function
		replace_conj_func(conll_tokens, tokoffset, lex)

		# Enrich tokens with modifiers and parent head text
		for token in conll_tokens[tokoffset:]:
			for child in children[token.id]:
				if lex.filters["mod_func"].match(conll_tokens[int(child)].func) is not None:
					token.modifiers.append(conll_tokens[int(child)])
			token.head_text = conll_tokens[int(token.head)].text

		# Find dead areas
		for tok1 in conll_tokens[tokoffset + 1:]:
			# Affix tokens can't be markable heads - assume parser error and fix if desired
			# DEBUG POINT
			if tok1.text.strip() == lex.debug["ana"]:
				pass
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
								if child in tok1.modifiers:
									tok1.modifiers.remove(child)
									child.modifiers.append(tok1)
								# Check if any other non-link parents need to be re-routed to the new head
								for tok_to_rewire in conll_tokens[tokoffset + 1:]:
									if tok_to_rewire.original_head == tok1.id and tok_to_rewire.head != child.id and tok_to_rewire.id != child.id:
										tok_to_rewire.head = child.id
										# Also add the rewired child func
										if tok_to_rewire.func not in child.child_funcs:
											child.child_funcs.append(tok_to_rewire.func)
										# Rewire modifiers
										if tok_to_rewire not in child.modifiers and lex.filters["mod_func"].match(tok_to_rewire.func) is not None:
											child.modifiers.append(tok_to_rewire)
										if child in tok_to_rewire.modifiers:
											tok_to_rewire.modifiers.remove(child)

								# Only do this for the first subordinate markable head found by traversing right to left
								break

			# Try to construct a longer stop candidate starting with each token in the sentence, max length 5 tokens
			stop_candidate = ""
			for tok2 in conll_tokens[int(tok1.id):min(len(conll_tokens),int(tok1.id)+4)]:
				stop_candidate += tok2.text + " "
				if stop_candidate.strip().lower() in lex.stop_list:  # Stop list matched, flag tokens as impossible markable heads
					for tok3 in conll_tokens[int(tok1.id):int(tok2.id) + 1]:
						stop_ids[tok3.id] = True

		# Find last-first name combinations
		for tok1 in conll_tokens[tokoffset + 1:-1]:
			tok2 = conll_tokens[int(tok1.id) + 1]
			first_name_candidate = tok1.text.title() if tok1.text.isupper() else tok1.text
			last_name_candidate = tok2.text.title() if tok2.text.isupper() else tok2.text
			if first_name_candidate in lex.first_names and last_name_candidate in lex.last_names and tok1.head == tok2.id:
				stop_ids[tok1.id] = True
		# Allow one intervening token, e.g. for middle initial
		for tok1 in conll_tokens[tokoffset + 1:-2]:
			tok2 = conll_tokens[int(tok1.id) + 2]
			first_name_candidate = tok1.text.title() if tok1.text.isupper() else tok1.text
			middle_name_candidate = conll_tokens[int(tok1.id) + 1].text.title() if tok1.text.isupper() else conll_tokens[int(tok1.id) + 1].text
			last_name_candidate = tok2.text.title() if tok2.text.isupper() else tok2.text
			if first_name_candidate in lex.first_names and last_name_candidate in lex.last_names and tok1.head == tok2.id and (re.match(r'^[A-Z]\.$',middle_name_candidate) or middle_name_candidate in lex.first_names):
				stop_ids[tok1.id] = True

		# Expand children list recursively into descendants
		for parent_key in children:
			if int(parent_key) > tokoffset:
				descendants[parent_key] = get_descendants(parent_key, children, [], self.sent_num, conll_tokens)

		keys_to_pop = []

		# Find markables
		for tok in conll_tokens[tokoffset + 1:]:
			# Markable heads should match specified pos or pos+func combinations,
			# ruling out stop list items with appropriate functions
			if tok.text.strip() == lex.debug["ana"]:
				pass
			# TODO: consider switch for lex.filters["stop_func"].match(tok.func)
			if ((lex.filters["mark_head_pos"].match(tok.pos) is not None and lex.filters["mark_forbidden_func"].match(tok.func) is None) or
					pos_func_combo(tok.pos, tok.func, lex.filters["pos_func_heads"])) and not (stop_ids[tok.id]):
				this_markable = make_markable(tok, conll_tokens, descendants, tokoffset, sentence, keys_to_pop, lex)
				if this_markable is not None:
					mark_candidates_by_head[tok.id] = this_markable

				# Check whether this head is the beginning of a coordination and needs its own sub-markable too
				make_submark = False
				submark_id = ""
				submarks = []
				cardi=0
				for child_id in children[tok.id]:
					child = conll_tokens[int(child_id)]
					if child.coordinate:
						# Coordination found - make a small markable for just this first head without coordinates
						make_submark = True
						# Remove the coordinate children from descendants of small markable head
						if child.id in descendants:
							for sub_descendant in descendants[child.id]:
								if tok.id in descendants:
									if sub_descendant in descendants[tok.id]:
										descendants[tok.id].remove(sub_descendant)
						if tok.id in descendants:
							if child.id in descendants[tok.id]:
								descendants[tok.id].remove(child.id)
						# Build a composite id for the large head from coordinate children IDs separated by underscore
						submark_id += "_" + child.id
						cardi+=1
						submarks.append(child.id)
				if make_submark:
					submarks.append(tok.id)
					# Assign aggregate/coordinate agreement class to large markable if desired
					# Remove coordination tokens, such as 'and', 'or' based on coord_func setting
					for child_id in children[tok.id]:
						child = conll_tokens[int(child_id)]
						if lex.filters["coord_func"].match(child.func):
							if child.id in descendants[tok.id]:
								descendants[tok.id].remove(child.id)

					# Make the small markable and recall the big markable
					mark_candidates_by_head[tok.id].cardinality=cardi+1
					big_markable = mark_candidates_by_head[tok.id]
					small_markable = make_markable(tok, conll_tokens, descendants, tokoffset, sentence, keys_to_pop, lex)
					big_markable.submarks = submarks[:]
					if lex.filters["aggregate_agree"] != "_":
						big_markable.agree = lex.filters["aggregate_agree"]
						big_markable.agree_certainty = "coordinate_aggregate_plural"
						big_markable.coordinate = True

					# Switch the id's so that the big markable has the 1_2_3 style id, and the small has just the head id
					mark_candidates_by_head[tok.id + submark_id] = big_markable
					mark_candidates_by_head[tok.id] = small_markable
					big_markable = None
					small_markable = None
					#submarks = None


		# Check for atomicity and remove any subsumed markables if atomic
		for mark_id in mark_candidates_by_head:
			mark = mark_candidates_by_head[mark_id]
			if mark.end > mark.start:  # No atomicity check if single token
				# Check if the markable has a modifier based entity guess
				modifier_based_entity = recognize_entity_by_mod(mark, lex, True)
				# Consider for atomicity if in atoms or has @ modifier, but not if it's a single token or a coordinate markable
				if (is_atomic(mark, lex.atoms, lex) or ("@" in modifier_based_entity and "_" not in mark_id)) and mark.end > mark.start:
					for index in enumerate(mark_candidates_by_head):
						key = index[1]
						# Note that the key may contain underscores if it's a composite, but those can't be atomic
						if key != mark.head.id and mark.start <= int(re.sub('_.*','',key)) <= mark.end and '_' not in key:
							if lex.filters["pronoun_pos"].match(conll_tokens[int(re.sub('_.*','',key))].pos) is None:  # Make sure we're not removing a pronoun
								keys_to_pop.append(key)
				elif len(modifier_based_entity) > 1:
					stoplist_prefix_tokens(mark, lex.entity_mods, keys_to_pop)

		for key in keys_to_pop:
			mark_candidates_by_head.pop(key, None)

		for mark_id in mark_candidates_by_head:
			mark = mark_candidates_by_head[mark_id]
			mark.text = mark.text.strip()
			mark.core_text = mark.core_text.strip()
			# DEBUG POINT
			if mark.text == lex.debug["ana"]:
				pass
			tok = mark.head
			if lex.filters["proper_pos"].match(tok.pos) is not None:
				mark.form = "proper"
				mark.definiteness = "def"
			elif lex.filters["pronoun_pos"].match(tok.pos) is not None:
				mark.form = "pronoun"
				# Check for explicit indefinite morphology in morph feature of head token
				if "indef" in mark.head.morph.lower():
					mark.definiteness = "indef"
				else:
					mark.definiteness = "def"
			else:
				mark.form = "common"
				# Check for explicit definite morphology in morph feature of head token
				if "def" in mark.head.morph.lower() and "indef" not in mark.head.morph.lower():
					mark.definiteness = "def"
					# Chomp definite information not to interfere with agreement
					mark.head.morph = re.sub("def","_",mark.head.morph)
				else:
					# Check if any children linked via a link function are definite markings
					children_are_def_articles = (lex.filters["definite_articles"].match(conll_tokens[int(maybe_article)].text) is not None for maybe_article in children[mark.head.id]+[mark.head.id]+[mark.start])
					if any(children_are_def_articles):
						mark.definiteness = "def"
					else:
						mark.definiteness = "indef"

			# Find agreement alternatives unless cardinality has set agreement explicitly already (e.g. to 'plural'/'dual' etc.)
			if mark.cardinality == 0 or mark.agree == '':
				mark.alt_agree = resolve_mark_agree(mark, lex)
			if mark.alt_agree is not None and mark.agree == '':
				mark.agree = mark.alt_agree[0]
			elif mark.alt_agree is None:
				mark.alt_agree = []
			if mark.agree != mark.head.morph and mark.head.morph != "_" and mark.head.morph != "--" and mark.agree != lex.filters["aggregate_agree"]:
				mark.agree = mark.head.morph
				mark.agree_certainty = "mark_head_morph"
				mark.alt_agree.append(mark.head.morph)

			#cardinality resolve, only resolve here if it hasn't been set before (as in coordination markable)
			if mark.cardinality == 0:
				mark.cardinality = resolve_cardinality(mark,lex)

			resolve_mark_entity(mark, conll_tokens, lex)
			if "/" in mark.entity:  # Lexicalized agreement information appended to entity
				if mark.agree == "" or mark.agree is None:
					mark.agree = mark.entity.split("/")[1]
				elif mark.agree_certainty == "":
					mark.alt_agree.append(mark.agree)
					mark.agree = mark.entity.split("/")[1]
				mark.entity = mark.entity.split("/")[0]
			elif mark.entity == lex.filters["person_def_entity"] and mark.agree == lex.filters["default_agree"] and mark.form != "pronoun":
				mark.agree = lex.filters["person_def_agree"]
			subclass = ""
			if "\t" in mark.entity:  # This is a subclass bearing solution
				subclass = mark.entity.split("\t")[1]
				mark.entity = mark.entity.split("\t")[0]
			if mark.entity == lex.filters["person_def_entity"] and mark.form != "pronoun":
				if mark.text in lex.names:
					mark.agree = lex.names[mark.text]
			if mark.entity == lex.filters["person_def_entity"] and mark.agree is None:
				no_affix_mark = remove_suffix_tokens(remove_prefix_tokens(mark.text, lex), lex)
				if no_affix_mark in lex.names:
					mark.agree = lex.names[no_affix_mark]
			if mark.entity == lex.filters["person_def_entity"] and mark.agree is None:
				mark.agree = lex.filters["person_def_agree"]
			if mark.form == "pronoun" and (mark.entity == "abstract" or mark.entity == ""):
				if mark.head.head in markables_by_head and lex.filters["subject_func"].match(mark.head.func) is not None:
					mark.entity = markables_by_head[mark.head.head].entity
			if mark.entity == "" and mark.core_text.upper() == mark.core_text and re.search("[A-ZÄÖÜ]",mark.core_text) is not None:  # Unknown all caps entity, guess acronym default
				mark.entity = lex.filters["all_caps_entity"]
				mark.entity_certainty = "uncertain"
			if mark.entity == "":  # Unknown entity, guess default
				mark.entity = lex.filters["default_entity"]
				mark.entity_certainty = "uncertain"
			if subclass == "":
				if mark.subclass == "":
					subclass = mark.entity
				else:
					subclass = mark.subclass
			if mark.func == "title":
				mark.entity = lex.filters["default_entity"]
			if mark.agree == "" and mark.entity == lex.filters["default_entity"]:
				mark.agree = lex.filters["default_agree"]

			if "ablations" in lex.debug:
				if "no_subclasses" in lex.debug["ablations"]:
					subclass = mark.entity
					mark.alt_subclasses = mark.alt_entities

			self.markcounter += 1
			self.groupcounter += 1
			this_markable = Markable("referent_" + str(self.markcounter), tok, mark.form,
									 mark.definiteness, mark.start, mark.end, mark.text, mark.core_text, mark.entity, mark.entity_certainty,
									 subclass, "new", mark.agree, mark.sentence, "none", "none", self.groupcounter,
									 mark.alt_entities, mark.alt_subclasses, mark.alt_agree,mark.cardinality,mark.submarks,mark.coordinate)
			markables.append(this_markable)
			markables_by_head[mark_id] = this_markable
			markstart_dict[this_markable.start].append(this_markable)
			markend_dict[this_markable.end].append(this_markable)


		for markable_head_id in markables_by_head:
			if int(re.sub('_.*','',markable_head_id)) > tokoffset:  # Resolve antecedent for current sentence markables
				current_markable = markables_by_head[markable_head_id]
				# DEBUG POINT
				if current_markable.text == lex.debug["ana"]:
					pass
				# Revise coordinate markable entities now that we have resolved all of their constituents
				if len(current_markable.submarks) > 0:
					assign_coordinate_entity(current_markable,markables_by_head)
				if antecedent_prohibited(current_markable, conll_tokens, lex) or (current_markable.definiteness == "indef" and lex.filters["apposition_func"].match(current_markable.head.func) is None and not lex.filters["allow_indef_anaphor"]):
					antecedent = None
				elif (current_markable.definiteness == "indef" and lex.filters["apposition_func"].match(current_markable.head.func) is not None and not lex.filters["allow_indef_anaphor"]):
					antecedent, propagation = find_antecedent(current_markable, markables, lex, "appos")
				else:
					antecedent, propagation = find_antecedent(current_markable, markables, lex)
				if antecedent is not None:
					if int(antecedent.head.id) < int(current_markable.head.id) or 'invert' in propagation:
						# If the rule specifies to invert
						if 'invert' in propagation:
							temp = antecedent
							antecedent = current_markable
							current_markable = temp
						current_markable.antecedent = antecedent
						current_markable.group = antecedent.group
						# Check for apposition function if both markables are in the same sentence
						if lex.filters["apposition_func"].match(current_markable.head.func) is not None and \
								current_markable.sentence.sent_num == antecedent.sentence.sent_num:
							current_markable.coref_type = "appos"
						elif current_markable.form == "pronoun":
							current_markable.coref_type = "ana"
						elif current_markable.coref_type == "none":
							current_markable.coref_type = "coref"
						current_markable.infstat = "giv"
					else:  # Cataphoric match
						current_markable.antecedent = antecedent
						antecedent.group = current_markable.group
						current_markable.coref_type = "cata"
						current_markable.infstat = "new"
				elif current_markable.form == "pronoun":
					current_markable.infstat = "acc"
				else:
					current_markable.infstat = "new"

				if current_markable.agree is not None and current_markable.agree != '':
					lex.last[current_markable.agree] = current_markable
				else:
					pass



