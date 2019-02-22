import os
import pickle
import random
from os.path import join

import chainer
import numpy as np

from network import Network, Classifier


class Controller:
    def __init__(self, params=None):
        # data/ and label/ resides under dir_path
        self.params = params or {}
        self.map = {'.': 0}
        self.net = Network()
        self.load()

    def process(self, path):
        data_path = join(path, 'data')
        label_path = join(path, 'label')

        if os.path.exists(join(path, "dataset.pkl")):
            dataset = pickle.load(open(join(path, "dataset.pkl"), "rb"))
            print("read dataset from .pkl")
            return dataset

        dataset = []
        for file_step, filename in enumerate(os.listdir(data_path)):
            file_data = open(data_path + '/' + filename, "r")
            file_label = open(label_path + '/' + filename, "r")
            sentences = file_data.read().split('\n')[:-1]
            labels = file_label.read().split('\n')[:-1]

            for index, (data_in, label_in) in enumerate(zip(sentences, labels)):
                if len(label_in) != self.params['word_cnt']:
                    print("warning: data block", len(label_in))
                    continue
                data_in += '.' * (self.params['word_cnt'] - len(data_in))
                data = []
                for step, (char, sign) in enumerate(zip(data_in, label_in)):
                    if char not in self.map:
                        self.map[char] = len(self.map)
                    data.append([self.map[char], int(sign)])
                dataset.append(data)

            print("#%04d file '%s', datasize %d*64 (%d)" % (file_step, filename, len(dataset), len(dataset) * 64))
        random.shuffle(dataset)
        pickle.dump(dataset, open(path + "/dataset.pkl", "wb"))
        pickle.dump(self.map, open(self.params['save_path'] + "/map.pkl", "wb"))
        return dataset

    def train(self):
        dataset = {'test': self.process(self.params['test_path']), 'train': self.process(self.params['train_path'])}
        batchset = [dataset['train'][step:step + self.params['batch_size']]
                    for step in range(0, len(dataset['train'] - self.params['batch_size'] + 1), self.params['batch_size'])]
        self.net = Classifier(Network())
        self.optim = chainer.optimizers.Adam()
        self.optim.setup(self.net)
        for epoch in range(self.params['epoch']):
            for step, batch in enumerate(batchset):
                batch = np.array(batch, dtype=int)
                data = batch[:, :, 0]
                label = batch[:, :, 1]
                self.net.predictor.reset_state()
                self.net.cleargrads()
                loss, accuracy = self.net(data, label)
                loss.backward()
                self.optim.update()
                print("#{:08d} step(epoch {:02d}) loss={:.8f} accuracy={:.8f}".format(step, epoch, loss.data, accuracy.data))
        self.save()

    def test(self, sentence):
        result, x = [], []
        for char in sentence:
            if char not in self.map:
                print(char, "not in map")
                return None
            else:
                x.append(self.map[char])
        self.net.reset_state()
        pred = self.net(np.array(x, dtype=int))

        buf = []
        for x, char in zip(pred.data, sentence):
            sign = np.where(x == x.max())[0][0]
            buf.append(char)
            if sign == 2:
                result.append("".join(buf))
                buf.clear()
        if buf:
            result.append("".join(buf))
        return result

    def save(self):
        chainer.serializers.save_npz(join(self.params['save_path'], self.params['name'] + '.model'), self.net.predictor)
        chainer.serializers.save_npz(join(self.params['save_path'], self.params['name'] + '.optim'), self.optim)

    def load(self):
        chainer.serializers.load_npz(join(self.params['save_path'], self.params['name'] + '.model'), self.net)
        self.map = pickle.load(open(join(self.params['save_path'], "map.pkl"), "rb"))
