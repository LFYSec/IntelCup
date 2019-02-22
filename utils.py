import json
import secrets
from os.path import join, dirname

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pymongo import MongoClient
from pymongo.database import Database

db, r = None, None


def init(new_db=None, redis_client=None):
    global db, r
    db = new_db
    r = redis_client


class AppError(Exception):
    def __init__(self, message):
        self.message = message

class AuthError(AppError):
    pass

def validate_email(email):
    return '@' in email


def connect_db(config=None) -> Database:
    if not config:
        with open(join(dirname(__file__), "config.json")) as f:
            config = json.load(f)
    return MongoClient(**(config["db"].get("connection", {})))[config["db"]["name"]]


def get_kdf(salt):
    return PBKDF2HMAC(algorithm=SHA256, length=32, salt=salt, iterations=2000, backend=default_backend())


def hash_password(password):
    if isinstance(password, str):
        password = password.encode("utf-8")
    salt = secrets.token_bytes(32)
    kdf = get_kdf(salt)
    return kdf.derive(password), salt


def verify_password(password, pwhash, salt):
    if isinstance(password, str):
        password = password.encode("utf-8")
    if isinstance(pwhash, str):
        pwhash = bytes.fromhex(pwhash)
    if isinstance(salt, str):
        salt = bytes.fromhex(salt)
    kdf = get_kdf(salt)
    try:
        kdf.verify(password, pwhash)
        return True
    except InvalidKey:
        return False


def new_id(length=32):
    return secrets.token_hex(length)


if __name__ == "__main__":
    pwhash, salt = hash_password("pass")
    assert verify_password("pass", pwhash, salt)
    assert not verify_password("pass1", pwhash, salt)
    from timeit import timeit

    print(timeit("verify_password(\"pass\", pwhash, salt)", number=1000, globals=globals()) / 1000)
