import logging
import pickle
import re
from io import StringIO
from time import time
from traceback import format_exc

from dateutil.parser import parse
from redis import Redis

from bayes import BayesFilter
from utils import connect_db

UUID_PATTERN = re.compile("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
EMOJI_NAMES = ["笑哭", "doge", "晕", "斜眼笑", "喷血", "微笑", "偷笑", "小纠结", "发抖", "衰", "幽灵", "蹭一蹭", "点赞", "抠鼻", "托腮", "泪奔", "发呆", "疑问",
               "拜托", "可爱", "呲牙", "抱拳", "拥抱", "捂脸", "磕头", "顶呱呱", "卖萌", "流汗", "猪头", "瓢虫", "憨笑", "羊驼", "糊脸", "药", "无聊", "托脸", "拽炸天",
               "扯一扯", "我最美", "亲亲", "灯笼", "冷汗", "骚扰", "流泪", "再见", "坏笑", "闭嘴", "好棒", "哈欠", "得意", "擦汗", "玫瑰", "赞", "不开心", "鼓掌", "尴尬",
               "无奈", "难过", "胜利", "可怜", "调皮", "悠闲", "脸黑", "害羞", "阴险", "饥饿", "撇嘴", "快哭了", "害怕", "委屈","转圈"]
NOGO_STRINGS = ["com.tencent.mobileqq", "撤回", "https://qun.qq.com", "已加入该群", "shouldDisplayIwSizeLcopy", "imageWidthJ", "dwMSGItem",
                "加入了本群", "gchatpic_new", "vip.qq.com", "分享自", "originMsgType", "qqwallet","qun.qq.com/qunpay","qun.qq.com/qqweb/m/qun/medal"]
NOGO_REGEXES = [re.compile(pattern) for pattern in ("https?:\/\/.+", "[0-9a-zA-Z_+.\-/ …<>#;~。？':(%,)\"&|=\[\]]+")]

STRIPPED_REGEXES = [re.compile(pattern) for pattern in ("\[.{1,6}?\]", r"##\*\*##[0-9a-zA-Z,]+", "[\x00-\x1f\x7f]+")]

METADATA_REGEX = re.compile(r"(\d{4}-\d{1,2}-\d{1,2} \d{2}:\d{2}:\d{2})  ([^\n]+)\((\d+)\)")
METADATA_REGEX_SPECIAL = re.compile(r"(\d{4}-\d{1,2}-\d{1,2} \d{2}:\d{2}:\d{2})  ([^\n]+)()")

FILE_METADATA_REGEX = re.compile("群名称:(.+)")

logger = logging.getLogger("parse")


def _to_lines(stream, sentinel=None):
    while True:
        line = stream.readline()
        if not line:
            break
        yield line.rstrip("\r\n")
    if sentinel:
        yield sentinel


def filter_line(line):
    for pattern in STRIPPED_REGEXES:
        line, _ = pattern.subn("", line)
    for pattern in EMOJI_NAMES:
        line = line.replace("/" + pattern, "")
    if any([x in line for x in NOGO_STRINGS]) or any([pattern.fullmatch(line) for pattern in NOGO_REGEXES]) or len(line) == 1 \
            or UUID_PATTERN.search(line) or line.count("�") > 1:
        return None
    else:
        return line.strip()


def parse_messages(data):
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    stream = StringIO(data)
    group_name = re.fullmatch("群名称:(.+)\n", stream.readline()).group(1).strip()
    stream.readline()
    ret = []
    msg = {}
    for line in _to_lines(stream, "---END---"):
        m = METADATA_REGEX.fullmatch(line)
        if not m:
            m = METADATA_REGEX_SPECIAL.fullmatch(line)
        if m or line == -1:
            if msg:
                if len(msg["content"]) and not msg["content"][-1]:
                    msg["content"].pop()
                if msg["content"]:
                    msg["content"] = "\n".join(msg["content"])
                    ret.append(msg.copy())
                msg.clear()
            if m:
                msg.update({"time": parse(m.group(1)), "author": m.group(2), "qq": m.group(3), "group": group_name, "content": []})
        else:
            filtered_line = filter_line(line)
            if filtered_line:
                msg["content"].append(filtered_line)
    return ret


if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    r = Redis()
    db = connect_db()
    bf = BayesFilter()
    while True:
        task = pickle.loads(r.blpop("parse_tasks")[1])
        try:
            parsed = parse_messages(task["data"])
            filtered = list(bf.filter_messages(parsed))
            for message in filtered:
                message["user_id"] = task["user_id"]
                message["date"] = message["time"].strftime("%Y-%m-%d")
                message["time"] = message["time"].strftime("%Y-%m-%d %H:%M:%S")
                if not db.messages.find_one({"$and": [{"user_id": message["user_id"]}, {"qq": message["qq"]}, {"time": message["time"]}]}):
                    db.messages.insert_one(message)
                    if message["author"] == message["qq"]:
                        r.rpush("nick_queries", message["qq"])
                else:
                    logger.debug("Skipped message from QQ:{}".format(message["qq"]))
            r.delete(f"user.{task['user_id']}.dates")
            logger.info(f"Processed chat log from {task['user_id']}, file size {len(parsed)}, {len(filtered)} messages remained.")
        except Exception:
            logger.error("Exception at {}".format(time()))
            logger.error(format_exc())
