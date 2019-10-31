



import os, sys, re, time, argparse
from datetime import timedelta
script_dir = os.path.dirname(os.path.realpath(__file__))
lib = os.path.abspath(script_dir + os.sep + "..")
sys.path.append(lib)


# from flair.data import TaggedCorpus
from flair.data import Corpus
from flair.datasets import ColumnCorpus
from flair.data_fetcher import NLPTaskDataFetcher, NLPTask
from flair.embeddings import TokenEmbeddings, WordEmbeddings, StackedEmbeddings, FlairEmbeddings, BertEmbeddings
from typing import List





class Sequencer:

    def __init__(self, lang="eng", model="eng.rst.gum", windowsize=5, use_words=False):
        self.data_dir = args.dir




    def get_data(self, data_dir, tag_type='ner', train_file='train.txt', dev_file='dev.txt', test_file='test.txt'):

        # customize data format, see
        # https://github.com/zalandoresearch/flair/blob/master/resources/docs/TUTORIAL_6_CORPUS.md#reading-your-own-sequence-labeling-dataset


        columns = {0: 'text', 1: 'pos', 2: 'deprel', 3: 'ner'}
        corpus: Corpus = ColumnCorpus(data_dir, columns, train_file=train_file, dev_file=dev_file, test_file=test_file)
        # print(corpus)


        # make the tag dictionary from the corpus
        tag_dictionary = corpus.make_tag_dictionary(tag_type=tag_type)
        # print(tag_dictionary.idx2item)



        # (TODO: TEST IF WORKS)  Some useful stats below:

        #  Obtain statistics about the dataset
        stats = corpus.obtain_statistics()
        print(stats)

        # check how many sentences there are in the training split
        len(corpus.train)

        # You can also access a sentence and check out annotations
        print(corpus.train[0].to_tagged_string('ner'))

        return corpus, tag_dictionary



    def initialize_embeddings(self, fastbert=True, stackedembeddings=True):


        # Consider using pooling_operation="first", use_scalar_mix=True for the parameters

        # initialize individual embeddings
        if fastbert:
            bert_embedding = BertEmbeddings('distilbert-base-uncased',  layers='-1')

        else:
            bert_embedding = BertEmbeddings('bert-base-cased', layers='-1')


        if stackedembeddings:
            glove_embedding = WordEmbeddings('glove')

            # init Flair forward and backwards embeddings
            flair_embedding_forward = FlairEmbeddings('news-forward')
            flair_embedding_backward = FlairEmbeddings('news-backward')

            embedding_types = [bert_embedding, glove_embedding, flair_embedding_forward, flair_embedding_backward]

            embeddings = StackedEmbeddings(embeddings=embedding_types)

        else:

            embeddings = bert_embedding


        return embeddings


    def initialize_sequence_tagger(self, embeddings, tag_dictionary, tag_type='ner'):
        from flair.models import SequenceTagger

        tagger: SequenceTagger = SequenceTagger(hidden_size=256,
                                                embeddings=embeddings,
                                                tag_dictionary=tag_dictionary,
                                                tag_type=tag_type,
                                                use_crf=True)

        return tagger




    def train(self, model_dir, tagger, corpus, max_epoch=150, gpu=True):

        # 6. initialize trainer
        from flair.trainers import ModelTrainer

        trainer: ModelTrainer = ModelTrainer(tagger, corpus)

        if gpu:
            embeddings_storage_mode = 'gpu'
        else:
            embeddings_storage_mode = 'cpu'


        # start training & save model to model_dir
        trainer.train(model_dir,
                      learning_rate=0.1,
                      mini_batch_size=32,
                      max_epochs=max_epoch,
                      embeddings_storage_mode=embeddings_storage_mode,
                      )



    def plot_curve(self, traing_curve_path = os.path.normpath(r'./resources/taggers/slow_bert/loss.tsv'), weights_path= os.path.normpath(r'./resources/taggers/slow_bert/loss.tsv')):

        from flair.visual.training_curves import Plotter
        plotter = Plotter()

        plotter.plot_training_curves(traing_curve_path)
        plotter.plot_weights(weights_path)







def predict(self, model_dir=os.path.normpath(r'.resources/taggers/slow_bert/final-model.pt'), input_string='I love Berlin'):

    from flair.models import SequenceTagger

    # load the model you trained
    tagger = SequenceTagger.load(model_dir)

    # create example sentence
    sentence = Sentence(input_string)

    # predict tags and print
    tagger.predict(sentence)

    print(sentence.to_tagged_string())




if __name__ == "__main__":


    start_time = time.time()

    # Logan's folder
    logandir = os.path.normpath(r'./gum_slim_UD/')

    # argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', '-d', default=logandir, help='Directory of train, dev, test files')
    parser.add_argument('--epoch', '-e', type=int, default=150, help='Max epoch for training')
    parser.add_argument('--mode', '-m', default='train', choices=['train', 'predict'], help='train or predict mode')
    parser.add_argument('--name', '-n', default='fast_bert', choices=['slow_bert', 'fast_bert', 'slow_stacked', 'fast_stacked'], help='directory name of the model')
    # parser.add_argument('--fastbert', '-f', action='store_true', help='fastbert if using distilbert')
    # parser.add_argument('--stackedembeddings', '-s', action='store_true', help='if using stackedembeddings')
    parser.add_argument('--gpu', '-g', action='store_true', help='if using gpu')


    args = parser.parse_args()


    if args.mode == 'train':
        sequencer = Sequencer()


        # 1. get the corpus: data_dir &  train_file, dev_file, test_file split
        sys.stdout.write('o Training on %s' % (args.dir))
        corpus, tag_dictionary = sequencer.get_data(args.dir, tag_type='ner', train_file='train.txt', dev_file='dev.txt', test_file='test.txt')



        # 2. initialize embeddings
        speed, embeds = args.name.split('_')

        sys.stdout.write('o Initializing embeddings with fastbert=%s and stackedembeddings=%s' % (speed, embeds))
        embeddings = sequencer.initialize_embeddings(fastbert=speed=='fast', stackedembeddings=embeds=='stacked')



        # 3. intialize sequence tagger
        sys.stdout.write('o Initializing sequence tagger')
        tagger= sequencer.initialize_sequence_tagger(embeddings=embeddings, tag_dictionary=tag_dictionary, tag_type='ner')


        # 4. train sequence tagger and save model to model_path
        sys.stdout.write('o Training sequence tagger with max_epoch=%d and gpu=%s' %(args.epoch, str(args.gpu)))
        sequencer.train(model_dir=os.path.normpath(r'./resources/taggers/'+args.name), tagger=tagger, corpus=corpus, max_epoch=args.epoch, gpu=args.gpu)
        sys.stdout.write('o Best model saved to %s' %(os.path.normpath(r'./resources/taggers/'+args.name)))


    else:

        predict(model_dir=os.path.normpath(r'.resources/taggers/' + args.name + '/final-model.pt'), input_string='I love Berlin')





    elapsed = time.time() - start_time
    sys.stderr.write("\n\no DONE! Total time elapsed for %s : " % (args.name) + str(timedelta(seconds=elapsed)) + "\n\n")


