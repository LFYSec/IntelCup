import os
import pickle
import re

from controller import Controller
from network import params


class BeyasFilter:
    # 0-ham 1-spam
    def __init__(self):
        self.controller = Controller(params)
        self.prior = 29411 / 1177
        self.threhold = 8
        self.ham_func = pickle.load(open("ham_func.pkl", "rb"))
        self.spam_func = pickle.load(open("spam_func.pkl", "rb"))
        if not self.load():
            self.count = [0, 0]
            self.freq = {}

    def segment(self, content):
        # content is a string
        # content=[self.thul.cut(x)[0][0] for x in content if x]
        content = content.replace("[分享]", '').replace("[emoji]", '').replace("[图片]", '')
        partten = ["/.{2}", "https://[0-9A-Za-z\.\?/#%&]+|http://[0-9A-Za-z\.\?/#%&]+|www[0-9A-Za-z\.\?/#%&]+"]
        result = []
        for p in partten:
            result += re.findall(p, content)
            content, number = re.subn(p, '', content)
        result += re.findall("[^\u4e00-\u9fa50-9A-Za-z-& ]|[&|-]{2,}", content)
        result += self.net(re.split("[^\u4e00-\u9fa50-9A-Za-z-&]|[&|-]{2,}", content))
        result = [x for x in result if x]
        return result

    def net(self, contents):
        result = []
        for snt in contents:
            if len(snt) <= 2:
                result.append(snt)
            else:
                x = self.controller.test(snt)
                if x: result += x
        return result

    def train(self, words, label):
        # label: 0-ham 1-spam
        for word in words:
            self.count[label] += 1
            if word not in self.freq:
                self.freq[word] = [0, 0]
            self.freq[word][label] += 1

    def test(self, snts, labels):
        sign = {"ham": False, "spam": True}
        correct = 0
        snt_sum = 0
        for snt, label in zip(snts, labels):
            if self.isspam(snt) == sign[label]:
                correct += 1
            snt_sum += 1
        print(correct / snt_sum)

    def isspam(self, content, total_length=0):
        pred = 1
        words = self.segment(content)
        for word in words:
            if self.freq.get(word) and self.freq[word][1] != 0 and self.freq[word][0] != 0:
                pred *= (self.freq[word][1] * self.count[0]) / (self.freq[word][0] * self.count[1])
            elif not self.freq.get(word):
                pred *= ((self.freq[word][1] + 1) * (self.count[0] + 1)) / ((self.freq[word][0] + 1) * (self.count[1] + 1))
            else:
                pred *= ((self.freq[word][1] + 1) * (self.count[0] + 1)) / ((self.freq[word][0] + 1) * (self.count[1] + 1))
        # return True if pred>1 else False
        if total_length == 0: total_length = len(content)
        return pred * self.lenfunc(total_length) * self.threhold  # *self.prior

    def lenfunc(self, length):
        # return 0.4+math.exp(self.func_a-self.func_b*length)
        # if length<=20: return self.threhold[0]
        # return self.threhold[1]
        if length > 400:
            return 1
        elif length <= 2:
            return 1000
        return self.ham_func[length] / self.spam_func[length]

    def save(self):
        pickle.dump(self.count, open("count.pkl", "wb"))
        pickle.dump(self.freq, open("freq.pkl", "wb"))
        print("module saved.")

    def load(self):
        if os.path.exists("count.pkl") and os.path.exists("freq.pkl"):
            self.count = pickle.load(open("count.pkl", "rb"))
            self.freq = pickle.load(open("freq.pkl", "rb"))
        else:
            print("not find module sourses.")
            return False
        print("module loaded.")
        return True

    def train_files(self, path, label):
        for count, filename in enumerate(os.listdir(path)):
            if count % 50 == 0:
                print("#%05d file '%s' done." % (count, filename))
            file = open(path + filename, "r")
            content = file.read().split('\n')
            content = self.segment(content)
            self.train(content, label)
        self.save()
        print(path, "dir done.")
