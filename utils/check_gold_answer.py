#!/usr/bin/python
# -*- coding: utf-8 -*-

import re, csv, sys, os
from collections import defaultdict

class CheckGoldAnswer:
    def __init__(self, file, gold_file, response_file):
        self.filename = file
        self.gold_file = gold_file
        self.response_file = response_file
        self.marks = self.read_gold_answer()
        self.check = self.check_gold_answer()

    def read_gold_answer(self):
        marks = {}
        docname = self.filename
        marks[docname] = {}
        cardinal = 1
        gold = open(self.gold_file, encoding='utf-8').readlines()
        index = 1
        for fields in gold:
            fields = fields.strip().split('\t')
            if len(fields) <= 1:continue
            if fields[0].startswith("#"):continue
            else:
                entity_type = fields[3]
                if '_' not in entity_type:
                    if '[' in entity_type:
                        entities = entity_type.split('|')
                        # Select all possible gold entity types from GUM
                        for entity_pre in entities:
                            entity = entity_pre.replace('[', '_')[:-1]
                            if entity not in marks[docname].keys():
                                marks[docname][entity] = []
                            marks[docname][entity].append(cardinal)
                    else:
                        entity = entity_type + '_' + str(index) + '_'
                        if entity not in marks[docname].keys():
                            marks[docname][entity] = []
                        marks[docname][entity].append(cardinal)
                        index += 1
            cardinal += 1
        # Convert marks to a more readable format for checking gold answers
        gold_entities = defaultdict(str)
        for name, doc in marks.items():
            gold_entities[name] = defaultdict(str)
            for entity, n in doc.items():
                gold_entities[name][(n[0], n[-1])] = {}
                gold_entities[name][(n[0], n[-1])] = entity.split('_')[0]
        sys.stderr.write('Finished reading gold entities.\n')
        return gold_entities

    def check_gazetteers(self, dump_column, positions):
        gold_gazetteers = []
        gazetteers_check = {}
        entity_gazetteers = csv.reader(open('..\\xrenner\\models\\udx\\entities.tab', 'r'))
        # entities = [row for row in entity_gazetteers]
        entity_heads_gazetteers = csv.reader(open('..\\xrenner\\models\\udx\\entity_heads.tab', 'r'))
        # entity_heads = [row for row in entity_heads_gazetteers]
        entity_mods_gazetteers = csv.reader(open('..\\xrenner\\models\\udx\\entity_mods.tab', 'r'))
        # entity_modss = [row for row in entity_mods_gazetteers]
        gold = open(self.gold_file, encoding='utf-8').readlines()
        for position in positions:
            cardinal = 1
            n_start = position[0]
            n_end = position[-1]
            tokens = []
            for fields in gold:
                fields = fields.strip().split('\t')
                if len(fields) <= 1:continue
                if fields[0].startswith("#"):continue
                else:
                    if cardinal >= n_start and cardinal <= n_end:
                        token = fields[2]
                        tokens.append(token)
                    if cardinal > n_end: break
                    cardinal += 1
            gazetteers_check[(n_start, n_end)] = tokens
        for i, headers in enumerate(dump_column):
            if headers[0] == self.filename:
                position = (int(headers[8]), int(headers[9]))
                for doc in self.marks:
                    for gold_position, gold_entity in self.marks[doc].items():
                        if position not in self.marks[doc].keys():
                            gold_gazetteers.append('_')
                            break
                        if position == gold_position:
                            for row in entity_gazetteers:
                                if " ".join(gazetteers_check[position]) == row[0]:
                                    gold_gazetteers.append(row[1])
                                    break
                            for row in entity_heads_gazetteers:
                                if " ".join(gazetteers_check[position]) == row[0]:
                                    gold_gazetteers.append(row[1])
                                    break
                            for row in entity_mods_gazetteers:
                                if " ".join(gazetteers_check[position]) == row[0]:
                                    gold_gazetteers.append(row[1])
                                    break

    def check_gold_answer(self):
        gold_answer_list = []
        position_list = []
        csvfile = csv.reader(open(self.response_file, 'r'))
        column = [row for row in csvfile]
        for i, row in enumerate(column):
            headers = row[:]
            if headers[0] == self.filename:
                position = (int(headers[8]), int(headers[9]))
                position_list.append(position)
                for doc in self.marks:
                    for gold_position, gold_entity in self.marks[doc].items():
                        # check positions and assign gold entities to the row
                        if position not in self.marks[doc].keys():
                            gold_answer_list.append('_')
                            break
                        if position == gold_position:
                            gold_answer_list.append(gold_entity)
                            break

        sys.stderr.write('Finished checking gold entities of %s, %d gold answers are checked.\n' %
                         (self.filename, len(gold_answer_list)))
        gold_gazetteers_check = self.check_gazetteers(position_list)

        # check gold gazetteers

        with open('dump_files\\%s.csv' % (self.filename), 'w') as f:
            reader = csv.reader(open(self.response_file, 'r'))
            writer = csv.writer(f, lineterminator='\n')
            n = 0
            for row in reader:
                if row[0] == self.filename:
                    row.append(gold_answer_list[n])
                    writer.writerow(row)
                    n += 1
        sys.stderr.write('Finished writing gold entities for %s.\n' % (self.filename))
        return 0


if __name__ == '__main__':
    train_files = open('..\\xrenner\\gum\\files_train.txt', 'r').readlines()
    for file in train_files:
        file = file.strip()
        gold_file = '..\\xrenner\\gum\\%s.tsv' % file
        response_file = '..\\xrenner\\dump_example_gum.csv'
        check_gold = CheckGoldAnswer(file, gold_file, response_file)
