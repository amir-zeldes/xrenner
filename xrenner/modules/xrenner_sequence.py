"""
modules/xrenner_sequence.py

Adapter class to accommodate sequence labeler
  * Supplies a uniform predict_proba() method
  * Reads serialized models
  * Compatible with flair embeddings

Author: Amir Zeldes
"""

import sys, os

class StdOutFilter(object):
	def __init__(self): #, strings_to_filter, stream):
		self.stream = sys.stdout
		self.stdout = sys.stdout

	def __getattr__(self, attr_name):
		return getattr(self.stream, attr_name)

	def write(self, data):
		output = []
		lines = data.split("\n")
		for line in lines:
			if "Epoch: " in line or (" f:" in line and "Test" not in line):
				output.append(line)
		if len(output)>0:
			data = "\n".join(output) + "\n"
			self.stream.write("RNN log - " + data.strip() + "\n")
			self.stream.flush()

	def flush(self):
		self.stream.flush()

	def start(self):
		sys.stdout = self

	def end(self):
		sys.stdout = self.stdout

p = StdOutFilter()
p.start()

# Silently import flair/torch
from flair.data import Sentence
from flair.models import SequenceTagger
import torch

p.end()


class Sequencer:
	def __init__(self, model_path=None):
		model_dir = os.sep.join([os.path.dirname(os.path.realpath(__file__)), "..", "models", "_embeddings"]) + os.sep
		if model_path is None:
			model_path = "best-model.pt"
		model_path = model_dir + model_path
		self.tagger = SequenceTagger.load_from_file(model_path)

	def clear_embeddings(self, sentences, also_clear_word_embeddings=False):
		"""
		Clears the embeddings from all given sentences.
		:param sentences: list of sentences
		"""
		for sentence in sentences:
			sentence.clear_embeddings(also_clear_word_embeddings=also_clear_word_embeddings)

	def predict_proba(self, sentences, mini_batch_size=32):
		"""
		Predicts a list of class and class probability tuples for every token in a list of sentences
		:param sentences: list of space tokenized sentence strings
		:param mini_batch_size: mini batch size to use
		:return: the list of sentences containing the labels
		"""

		# Sort sentences and keep order
		sents = [(len(s.split()),i,s) for i, s in enumerate(sentences)]
		sents.sort(key=lambda x:x[0], reverse=True)
		sentences = [s[2] for s in sents]

		with torch.no_grad():
			if type(sentences) is Sentence:
				sentences = [sentences]
			if isinstance(sentences[0],str):
				sentences = [Sentence(s) for s in sentences]

			batches = [sentences[x:x + mini_batch_size] for x in range(0, len(sentences), mini_batch_size)]
			featmats = []

			for i, batch in enumerate(batches):

				with torch.no_grad():
					feature, lengths, tags = self.tagger.forward(batch, sort=True)
					#loss = self._calculate_loss(feature, lengths, tags)
					tags = self.tagger._obtain_labels(feature, lengths)

					featmats.append(feature)

				for (sentence, sent_tags) in zip(batch, tags):
					for (token, tag) in zip(sentence.tokens, sent_tags):

						token.add_tag_label(self.tagger.tag_type, tag)

				# clearing token embeddings to save memory
				self.clear_embeddings(batch, also_clear_word_embeddings=True)

		# sort back
		sents = [tuple(list(sents[i]) + [s]) for i, s in enumerate(sentences)]
		sents.sort(key=lambda x:x[1])
		sents = [s[3] for s in sents]

		output = []
		for s in sents:
			for tok in s.tokens:
				output.append((tok.tags['ner'].value.replace("S-",""), tok.tags['ner'].score))

		return output


if __name__ == "__main__":
	c = Sequencer()
	x = c.predict_proba(["Mary had a little lamb","Her fleece was white as snow .","I joined Intel in the Age of Knives"])
	print(x)
