from os.path import join, dirname

import chainer
from chainer import functions
from chainer import links
from chainer import reporter

path = dirname(__file__)
params = {
    "name": "segment",
    "save_path": join(path, "saved"),
    "word_cnt": 48,
}


class Network(chainer.Chain):
    def __init__(self):
        super(Network, self).__init__()
        with self.init_scope():
            self.embed = links.EmbedID(8000, 512)
            self.rnn = links.LSTM(512, 256)
            self.linear = links.Linear(256, 64)
            self.out = links.Linear(64, 5)

    def reset_state(self):
        self.rnn.reset_state()

    def __call__(self, x):
        x = self.embed(x)
        x = self.rnn(x.reshape((-1, 512)))
        x = functions.relu(self.linear(x))
        x = self.out(x)
        return x


class Classifier(chainer.Chain):
    def __init__(self, predictor):
        super(Classifier, self).__init__()
        with self.init_scope():
            self.predictor = predictor

    def __call__(self, x, t):
        x = self.predictor(x)

        t = t.reshape((params['word_cnt'] * params['batch_size']))
        loss = functions.softmax_cross_entropy(x, t)
        accuracy = functions.accuracy(x, t)
        reporter.report({'loss': loss, 'accuracy': accuracy}, self)

        return loss, accuracy
