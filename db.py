import pickle
from time import time

from msgpack import unpackb, packb
from pymongo.database import Database
from redis import Redis

from utils import verify_password, AppError, AuthError, hash_password, new_id

db = None
r = None


def init(db_p: Database, rc: Redis):
    global db, r
    if not db:
        db = db_p
    else:
        print("DB re-inited.")
    if not r:
        r = rc
    else:
        print("Redis re-inited.")


def ensure_indexes():
    for key in ("username", "email", "id"):
        db.users.create_index([(key, 1)])
    for key in ("user_id", "token", "timestamp"):
        db.tokens.create_index([(key, 1)])


def check_password(username, password):
    """
    Check the validity of a username-password pair
    :param username:
    :param password:
    :return: DB document of user if valid
    """
    user = db.users.find_one({"$or": [{"username": username}, {"email": username}]})
    if not user or not verify_password(password, user["pwhash"], user["salt"]):
        raise AuthError("用户名/密码错误")
    else:
        db.logs.insert_one({"timestamp": time(), "action": "login", "username": username})
        user.pop("_id")
        return user


def new_user(email, username, password):
    """
    Create a new user.
    :param email: The user's email
    :param username: The user's username
    :param password: The user's password
    :return: ID of the new user
    """
    if len(password) < 8:
        raise AppError("密码长度至少为8个字符")
    if db.users.find_one({"$or": [{"username": username}, {"email": email}]}):
        raise AppError("用户名/邮箱已被使用")
    pwhash, salt = hash_password(password)
    user_id = new_id()
    db.users.insert_one({"id": user_id, "username": username, "email": email, "pwhash": pwhash.hex(), "salt": salt.hex(), "registered_timestamp": time()})
    log("register", username=username, email=email, user_id=user_id)
    return user_id


def get_messages(user_id, date):
    """
    Get all messages belonging to a user.
    :param user_id: ID of user
    :param date: A date string with a %Y-%m-%d format
    :return: A list of messages
    """
    messages = []
    for message in db.messages.find({"user_id": user_id, "date": date}):
        message.pop("_id")
        messages.append(message)
    return messages


def get_dates(user_id):
    """
    Get all dates on which the user have archived messages.
    :param user_id:
    :return:
    """
    cached_dates = r.get(f"user.{user_id}.dates")
    if cached_dates:
        return unpackb(cached_dates, raw=False)
    else:
        dates = set()
        for message in db.messages.find({"user_id": user_id}):
            dates.add(message["date"])
        dates = sorted(list(dates))
        r.set(f"user.{user_id}.dates", packb(dates, use_bin_type=True), ex=5 * 60)
        return dates


def get_surrounding_days(user_id, date):
    all_dates = get_dates(user_id)
    if not date in all_dates:
        return None, None
    index = all_dates.index(date)
    prev_day = all_dates[index - 1] if index >= 1 else None
    next_day = all_dates[index + 1] if index < len(all_dates) - 1 else None
    return prev_day, next_day


def get_token(user_id, lifespan=60 * 60 * 24 * 14):
    """
    Get a existing valid token or generate a new one. Doesn't check permission.
    :param user_id: ID of user
    :return: A token in the form of a hex string
    """
    token = (r.get(f"user.{user_id}.token") or b"").decode("utf-8")
    if token:
        return token
    else:
        token = new_id(64)
        p = r.pipeline()
        p.set(f"user.{user_id}.token", token, ex=lifespan)
        p.set(f"token.{token}.user_id", user_id, ex=lifespan)
        p.execute()
        return token


def token_to_user_id(token):
    token = (r.get(f"token.{token}.user_id") or b"").decode("utf-8")
    if token:
        return token
    else:
        return None


def new_parse_task(user_id, data):
    r.delete(f"user.{user_id}.dates")
    r.rpush("parse_tasks", pickle.dumps({"user_id": user_id, "data": data}))
    log("parse", user_id=user_id, size=len(data))


def log(action, **kw):
    log = {"timestamp": time(), "action": action}
    log.update(kw)
    db.logs.insert_one(log)


def change_password(user_id, new_password):
    pwhash, salt = hash_password(new_password)
    db.users.update_one({"id": user_id}, {"$set": {"pwhash": pwhash.hex(), "salt": salt.hex()}})
    log("password_change", user_id=user_id)


def recheck_password(user_id, password):
    user = db.users.find_one({"id": user_id})
    return user and verify_password(password, user["pwhash"], user["salt"])


def get_user(user_id):
    return db.users.find_one({"id": user_id})


def search_messages(user_id, criteria):
    query = {"user_id": user_id}
    query.update(criteria)
    return db.messages.find(query)
