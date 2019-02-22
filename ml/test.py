import os
import re
from os.path import join

from bayes import BayesFilter
from network import path

paths = {
    "ham": join(path, "data/ham/"),
    "spam": join(path, "data/spam/"),
}
labels = {
    "ham": 0,
    "spam": 1,
}
bfilter = BayesFilter()

# for key, p in paths.items():
# 	for filename in os.listdir(p):
# 		file=open(p+filename, "r")
# 		splited=re.split("<split>", file.read())
# 		for content in splited:
# 			seg=bfilter.segment(content)
# 			bfilter.train(seg, labels[key])
# 		print(filename, "done.")
# bfilter.save()

dataset = {"snts": [], "labels": []}
for key, p in paths.items():
    for filename in os.listdir(p):
        file = open(p + filename, "r")
        splited = re.split("<split>", file.read())
        for content in splited:
            dataset["snts"].append(content)
            dataset["labels"].append(key)
bfilter.test(dataset["snts"], dataset["labels"])
