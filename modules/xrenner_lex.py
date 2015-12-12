import csv
import gc
import os
import re
import ConfigParser
import sys
from collections import defaultdict

"""
xrenner - eXternally configurable REference and Non Named Entity Recognizer
LexData class - container object for lexical information, gazetteers etc.
Author: Amir Zeldes
"""


class LexData:
	"""
	Class to hold lexical information from gazetteers and training data.
	Use model argument to define subdirectory under modes/ for reading different sets of
	configuration files.
	"""
	def __init__(self, model,override=None):
		self.model = model
		self.atoms = {}
		self.entities = self.read_delim('entities.tab', 'triple')
		self.entity_heads = self.read_delim('entity_heads.tab', 'double')
		self.names = self.read_delim('names.tab')
		self.stop_list = self.read_delim('stop_list.tab', 'low')
		self.open_close_punct = self.read_delim('open_close_punct.tab')
		self.open_close_punct_rev = {v: k for k, v in self.open_close_punct.items()}
		self.entity_mods = self.read_delim('entity_mods.tab')
		self.entity_deps = self.read_delim('entity_deps.tab','quadruple')
		self.coref = self.read_delim('coref.tab')
		self.coref_rules = self.parse_coref_rules(self.read_delim('coref_rules.tab', 'single'))
		self.pronouns= self.read_delim('pronouns.tab', 'double')
		self.affix_tokens = self.read_delim('affix_tokens.tab')

		self.filters = self.get_filters(override)

		self.antonyms = self.read_antonyms()
		self.isa = self.read_isa()  # isa dictionary, from generic subclass string to list of valid substitutes

		self.atoms = self.get_atoms()
		first_last = self.get_first_last_names(self.names)
		self.first_names = first_last[0]
		self.last_names = first_last[1]

		self.pos_agree_mappings = self.get_pos_agree_mappings()
		self.last = {}

		self.morph = self.get_morph()
		self.func_substitutes_forward, self.func_substitutes_backward = self.get_func_substitutes()

		self.debug = self.read_delim('debug.tab')

	def read_delim(self, filename, mode="normal"):
		with open(os.path.dirname(os.path.realpath(__file__)) + os.sep + ".." + os.sep + "models" + os.sep + self.model + os.sep + filename, 'rb') as csvfile:
			reader = csv.reader(csvfile, delimiter='\t', escapechar="\\")
			if mode == "low":
				return dict((rows[0].lower(), "") for rows in reader if not rows[0].startswith('#') and not len(rows[0]) == 0)
			elif mode == "single":
				return list((rows[0]) for rows in reader if not rows[0].startswith('#') and not len(rows[0].strip()) == 0)
			elif mode == "double":
				out_dict = {}
				for rows in reader:
					if not rows[0].startswith('#') and not len(rows[0]) == 0:
						if rows[0] in out_dict:
							out_dict[rows[0]].append(rows[1])
						else:
							out_dict[rows[0]] = [rows[1]]
				return out_dict
			elif mode == "triple":
				out_dict = {}
				for rows in reader:
					if not rows[0].startswith('#'):
						if rows[2].endswith('@'):
							rows[2] = rows[2][0:-1]
							self.atoms[rows[0]] = rows[1]
						if rows[0] in out_dict:
							out_dict[rows[0]].append(rows[1] + "\t" + rows[2])
						else:
							out_dict[rows[0]] = [rows[1] + "\t" + rows[2]]
				return out_dict
				# Return dict((rows[0], rows[1]+"\t"+rows[2]) for rows in reader if not rows[0].startswith('#'))
			elif mode == "quadruple":
				out_dict = defaultdict(dict)
				#dep_dict = {}
				for rows in reader:
					if rows[0] == "in":
						pass
					if not rows[0].startswith('#'):
						#dep_dict[rows[1]] = [rows[2], rows[3]]
						if rows[0] in out_dict:
							if rows[1] in out_dict[rows[0]]:
								if int(rows[3]) > int(out_dict[rows[0]][rows[1]][1]):
									out_dict[rows[0]] = {rows[1] :[rows[2], rows[3]]}
							else:
								out_dict[rows[0]][rows[1]] =[rows[2], rows[3]]
						else:
							out_dict[rows[0]] = ({rows[1] :[rows[2], rows[3]]})
				return out_dict
			else:
				return dict((rows[0], rows[1]) for rows in reader if not rows[0].startswith('#'))

	def get_atoms(self):
		atoms = self.atoms
		places = dict((key, value[0]) for key, value in self.entities.items() if value[0].startswith(self.filters["place_def_entity"]+"\t"))
		atoms.update(places)
		atoms.update(self.names)
		persons = dict((key, value[0]) for key, value in self.entities.items() if value[0].startswith(self.filters["person_def_entity"]+"\t"))
		atoms.update(persons)
		organizations = dict((key, value[0]) for key, value in self.entities.items() if value[0].startswith(self.filters["organization_def_entity"]+"\t"))
		atoms.update(organizations)
		objects = dict((key, value[0]) for key, value in self.entities.items() if value[0].startswith(self.filters["object_def_entity"]+"\t"))
		atoms.update(objects)
		return atoms

	@staticmethod
	def get_first_last_names(names):
		firsts = {}
		lasts = []
		gc.disable()
		for name in names:
			if " " in name:
				parts = name.split(" ")
				firsts[parts[0]] = names[name]  # Get heuristic gender for this first name
				lasts.append(parts[len(parts)-1])  # Last name is a list, no gender info
		gc.enable()
		return [firsts,lasts]

	def read_antonyms(self):
		set_list = self.read_delim('antonyms.tab', 'low')
		output = {}
		for antoset in set_list:
			members = antoset.split(",")
			for member in members:
				if member not in output:
					output[member] = []
				for member2 in members:
					if member != member2:
						output[member].append(member2.lower())
		return output

	def read_isa(self):
		isa_list = self.read_delim('isa.tab')
		output = {}
		for isa in isa_list:
			output[isa] = []
			members = isa_list[isa].split(",")
			for member in members:
				output[isa].append(member.lower())
		return output

	def get_filters(self, override=None):
		#e.g., override = 'OntoNotes'
		config = ConfigParser.ConfigParser()
		config.read(os.path.dirname(os.path.realpath(__file__)) + os.sep + ".." + os.sep + "models" + os.sep + self.model + os.sep + 'config.ini')
		filters = {}
		options = config.options("main")

		if override:
			config_ovrd = ConfigParser.ConfigParser()
			config_ovrd.read(os.path.dirname(os.path.realpath(__file__)) + os.sep + ".." + os.sep + "models" + os.sep + self.model + os.sep + 'override.ini')
			try:
				options_ovrd = config_ovrd.options(override)
			except ConfigParser.NoSectionError:
				sys.stderr.write("\nNo section " +  override + " in override.ini in model " + self.model + "\n")
				sys.exit()


		for option in options:
			if override and option in options_ovrd:
				try:
					option_string = config_ovrd.get(override, option)
					if option_string == -1:
						pass
					else:
						if option_string.startswith("/") and option_string.endswith("/"):
							option_string = option_string[1:-1]
							filters[option] = re.compile(option_string)
						elif option_string == "True" or option_string == "False":
							filters[option] = config_ovrd.getboolean(override, option)
						elif option_string.isdigit():
							filters[option] = config_ovrd.getint(override, option)
						else:
							filters[option] = option_string
				except:
					print("exception on %s!" % option)
					filters[option] = None
				continue





			try:
				option_string = config.get("main", option)
				if option_string == -1:
					pass
				else:
					if option_string.startswith("/") and option_string.endswith("/"):
						option_string = option_string[1:-1]
						filters[option] = re.compile(option_string)
					elif option_string == "True" or option_string == "False":
						filters[option] = config.getboolean("main", option)
					elif option_string.isdigit():
						filters[option] = config.getint("main", option)
					else:
						filters[option] = option_string
			except:
				print("exception on %s!" % option)
				filters[option] = None

		return filters

	def lemmatize(self, token):

		lemma_rules = self.filters["lemma_rules"]
		lemma = token.text
		for rule in lemma_rules.split(";"):
			rule_part = rule.split("/")
			pos_pattern = re.compile(rule_part[0])
			if pos_pattern.search(token.pos):
				lemma_pattern = re.compile(rule_part[1])
				lemma = lemma_pattern.sub(rule_part[2], lemma)
		if self.filters["auto_lower_lemma"] == "all":
			return lemma.lower()
		elif self.filters["auto_lower_lemma"] == "except_all_caps":
			if lemma.upper() == lemma:
				return lemma
			else:
				return lemma.lower()
		else:
			return lemma

	def get_func_substitutes(self):

		substitutions_forward = {}
		substitutions_backward = {}
		subst_rules = self.filters["func_substitute_forward"]
		for rule in subst_rules.split(";"):
			rule_part = rule.split("/")
			substitutions_forward[rule_part[0]] = [rule_part[1],rule_part[2]]
		subst_rules = self.filters["func_substitute_backward"]
		for rule in subst_rules.split(";"):
			rule_part = rule.split("/")
			substitutions_backward[rule_part[0]] = [rule_part[1],rule_part[2]]
		return [substitutions_forward,substitutions_backward]

	def process_morph(self, token):

		morph_rules = self.filters["morph_rules"]
		morph = token.morph
		for rule in morph_rules.split(";"):
			rule_part = rule.split("/")
			morph = re.sub(rule_part[0], rule_part[1], morph)
		return morph

	def get_pos_agree_mappings(self):

		mappings = {}
		rules = self.filters["pos_agree_mapping"]
		for rule in rules.split(";"):
			if ">" in rule:
				mappings[rule.split(">")[0]] = rule.split(">")[1]

		return mappings

	@staticmethod
	def parse_coref_rules(rule_list):

		output=[]
		for rule in rule_list:
			output.append(rule.split(";"))

		return output

	def get_morph(self):
		morph = {}
		for head in self.entity_heads:
			for i in range(1, self.filters["max_suffix_length"]):
				if len(head) > i:
					substring = head[len(head)-i:]
					entity_list = self.entity_heads[head]
					if substring in morph:
						for entity in entity_list:
							if entity in morph[substring]:
								morph[substring][entity] += 1
							else:
								morph[substring][entity] = 1
					else:
						for entity in entity_list:
							morph[substring] = {entity:1}
		return morph