import json
import logging
import re
import traceback

from redis import Redis
from requests import Session

from utils import connect_db

if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    r = Redis()
    s = Session()
    db = connect_db()
    PATTERN = re.compile("portraitCallBack\((.+)\)")
    while True:
        qq = r.blpop("nick_queries")[1].decode("utf-8")
        try:
            ret = s.get("http://r.pengyou.com/fcg-bin/cgi_get_portrait.fcg?uins={}".format(qq), timeout=7)
            ret.encoding = "gbk"
            o = json.loads(PATTERN.fullmatch(ret.text).group(1))
            for item in o[qq]:
                if isinstance(item, str) and not item.startswith("http"):
                    r.set("nick.{}".format(qq), item)
                    db.messages.update_one({"author": qq, "qq": qq}, {"$set": {"author": item}})
        except Exception as e:
            logging.error("{} {}".format(repr(type(e)), repr(e)))
            logging.error(traceback.format_exc())
