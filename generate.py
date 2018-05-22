import inspect
import os

description_list = []

# Foreach folder (not hidden)
for f in os.listdir(os.getcwd()):
    if os.path.isdir(f) and not f.startswith('.'):
        for filename in os.listdir(f):
            if filename.endswith(".py"):
                print("{0} : {1}".format(filename, inspect.getcomments("{0}.{1}".format(f, filename))))