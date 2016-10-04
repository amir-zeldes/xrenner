from setuptools import setup, find_packages

setup(
  name = 'xrenner',
  packages = find_packages() + [models],
  version = '1.4.1.5',
  description = 'A configurable, language independent coreferencer and (non) named entity recognizer',
  author = 'Amir Zeldes',
  author_email = 'amir.zeldes@georgetown.edu',
  package_data = {'':['models/*.*','README.rst','LICENSE.txt','doc/*.*','test/*.*','licenses/*.*']}
  url = 'https://github.com/amir-zeldes/xrenner', 
  license='Apache License, Version 2.0',
  download_url = 'https://github.com/amir-zeldes/xrenner/tarball/1.4.1.5',
  keywords = ['NLP', 'coreference', 'NER', 'named entity'],
  classifiers = ['Programming Language :: Python',
'Programming Language :: Python :: 2',
'License :: OSI Approved :: Apache Software License',
'Operating System :: OS Independent'],
)