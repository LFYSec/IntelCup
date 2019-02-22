from bayes import BayesFilter
from parse import parse_messages

bf = BayesFilter()
with open("/tmp/out.txt", "w") as f:
    for x in parse_messages(open("/home/zhenyan/chat.txt").read()):
        content = x["content"]
        if "�" in content:
            print(repr(content))
