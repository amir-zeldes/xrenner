from setuptools import setup, find_packages

setup(
  name = 'xrenner',
  packages = find_packages(),
  version = '2.2.0.0',
  description = 'A configurable, language independent coreferencer and (non) named entity recognizer',
  author = 'Amir Zeldes',
  author_email = 'amir.zeldes@georgetown.edu',
  package_data = {'':['README.rst','LICENSE.txt'],'xrenner':['models/*','test/*','licenses/*','models/_sequence_taggers/*']},
   install_requires=['scikit-learn>=0.22.1','xgboost==0.90','flair==0.6.1','xmltodict'],
  url = 'https://github.com/amir-zeldes/xrenner',
  license='Apache License, Version 2.0',
  download_url = 'https://github.com/amir-zeldes/xrenner/releases/tag/v2.2.0.0',
  keywords = ['NLP', 'coreference', 'NER', 'named entity'],
  classifiers = ['Programming Language :: Python',
'Programming Language :: Python :: 2',
'Programming Language :: Python :: 3',
'License :: OSI Approved :: Apache Software License',
'Operating System :: OS Independent'],
)