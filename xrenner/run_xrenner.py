import os
from subprocess import call

train_files = open('gum\\files_train.txt', 'r').readlines()
path = "C:\\Documents\\Georgetown University\\Fall 2018\\Labs\\Corpling@GU\\gum\\dep\\stanford\\"
for file in train_files:
    file = file.strip()
    file_path = path + file + '.conll10'
    # os.system('python xrenner.py -o html %s' % (file_path))
    call(['python', 'xrenner.py', '-o html', '%s' % (file_path)])