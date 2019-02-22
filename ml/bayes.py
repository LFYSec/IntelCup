import os
import pickle
import re
from logging import getLogger
from math import log, exp

from controller import Controller
from network import params

logger = getLogger("bayes")


class BayesFilter:
    def __init__(self):
        self.controller = Controller(params)
        if not self.load():
            self.count = [0, 0]
            self.freq = {}

    def segment(self, content):
        content = content.replace("[分享]", '').replace("[emoji]", '').replace("[图片]", '')
        pattern = ["/.{2}", "https://[0-9A-Za-z\.\?/#%&]+|http://[0-9A-Za-z\.\?/#%&]+|www[0-9A-Za-z\.\?/#%&]+"]
        result = []
        for p in pattern:
            result += re.findall(p, content)
            content, number = re.subn(p, '', content)
        result += re.findall("[^\u4e00-\u9fa50-9A-Za-z-& ]|[&|-]{2,}", content)
        result += self.net(re.split("[^\u4e00-\u9fa50-9A-Za-z-&]|[&|-]{2,}", content))
        return [x for x in result if x]

    def net(self, contents):
        result = []
        for snt in contents:
            if len(snt) <= 2:
                result.append(snt)
            else:
                x = self.controller.test(snt)
                if x:
                    result += x
        return result

    def train(self, words, label):
        # labels: 0:ham,1:spam
        for word in words:
            self.count[label] += 1
            if word not in self.freq:
                self.freq[word] = [0, 0]
            self.freq[word][label] += 1

    def test(self, snts, labels):
        sign = {"ham": False, "spam": True}
        correct, snt_sum = 0, 0
        for snt, label in zip(snts, labels):
            if self.is_spam(snt) == sign[label]:
                correct += 1
            snt_sum += 1
        logger.info(str(correct / snt_sum))

    def filter_messages(self, messages):
        for message in messages:
            if not self.is_spam(message["content"]):
                yield message

    def is_spam(self, content):
        pred = 1
        words = self.segment(content)
        for word in words:
            if self.freq.get(word) and self.freq[word][1] != 0 and self.freq[word][0] != 0:
                pred *= (self.freq[word][1] * self.count[0]) / (self.freq[word][0] * self.count[1])
        pred = pred * (1 + exp(7 * log(10) - (3 / 5 * log(10)) * len(content))) * 1000
        return True if pred > 1 else False

    def save(self):
        pickle.dump(self.count, open("count.pkl", "wb"))
        pickle.dump(self.freq, open("freq.pkl", "wb"))
        logger.info("model saved")

    def load(self):
        if os.path.exists("count.pkl") and os.path.exists("freq.pkl"):
            self.count = pickle.load(open("count.pkl", "rb"))
            self.freq = pickle.load(open("freq.pkl", "rb"))
        else:
            raise FileNotFoundError("model is missing")
        logger.info("model loaded")
        return True

    def train_files(self, path, label):
        for count, filename in enumerate(os.listdir(path)):
            if count % 50 == 0:
                logger.info("#{} file '{}' done.".format(count, filename))
            file = open(path + filename, "r")
            content = file.read().split('\n')
            content = self.segment(content)
            self.train(content, label)
        self.save()
        logger.info("{} processed".format(path))
