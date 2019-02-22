import msgpack
from flask.sessions import SessionMixin, SessionInterface
from itsdangerous import Signer, BadSignature
from redis import Redis

from utils import new_id


class InMemorySession(dict, SessionMixin):
    def __init__(self, *kargs, **kwargs):
        self.id = new_id()
        super().__init__(*kargs, **kwargs)


class InMemorySessionManager(SessionInterface):
    def __init__(self):
        self._sessions = {}

    def open_session(self, app, request):
        signed_id = request.cookies.get(app.session_cookie_name)
        if not signed_id:
            return InMemorySession()
        try:
            signer = Signer(app.secret_key)
            session_id = signer.unsign(signed_id).decode("utf-8")
            if session_id in self._sessions:
                return self._sessions[session_id]
            else:
                return InMemorySession()
        except BadSignature:
            return InMemorySession()

    def save_session(self, app, session, response):
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        if not session:
            if session.modified:
                response.delete_cookie(app.session_cookie_name, domain=domain, path=path)
            return
        self._sessions[session.id] = session
        response.vary.add('Cookie')
        signer = Signer(app.secret_key)
        signed_id = signer.sign(session.id.encode("utf-8"))
        expires = self.get_expiration_time(app, session)
        response.set_cookie(app.session_cookie_name, signed_id, httponly=True, secure=False, samesite="STRICT", expires=expires)


class RedisSessionManager(SessionInterface):
    def __init__(self, r: Redis):
        self.r = r

    def open_session(self, app, request):
        signed_id = request.cookies.get(app.session_cookie_name)
        if not signed_id:
            return Session(new=True)
        try:
            signer = Signer(app.secret_key)
            session_id = signer.unsign(signed_id)
            if self.r.exists(b"session." + session_id):
                return msgpack.unpackb(self.r.get(b"session." + session_id), object_hook=unpack_hook, raw=False)
            else:
                return Session(new=True)
        except BadSignature:
            return Session(new=True)

    def save_session(self, app, session, response):
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        if not session:
            if not session.new:
                response.delete_cookie(app.session_cookie_name, domain=domain, path=path)
            return
        self.r.set("session." + session.id, msgpack.packb(session, default=pack_hook, use_bin_type=True))
        response.vary.add('Cookie')
        signer = Signer(app.secret_key)
        signed_id = signer.sign(session.id.encode("utf-8"))
        expires = self.get_expiration_time(app, session)
        response.set_cookie(app.session_cookie_name, signed_id, httponly=True, secure=False, samesite="STRICT", expires=expires)


class Session:
    new = False
    modified = True
    permanent = True

    def __init__(self, data=None, id=None, new=False):
        self.data = data or {}
        self.id = id or new_id()
        self.new = new

    def dump(self):
        return {"type": "session", "id": self.id, "data": self.data}

    def __getattr__(self, item):
        return getattr(self.data, item)

    def __getitem__(self, item):
        return self.data[item]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __delitem__(self, key):
        self.data.pop(key)

    def __iter__(self):
        return iter(self.data)

    def __contains__(self, item):
        return item in self.data

    def __len__(self):
        return len(self.data)

    def __eq__(self, other):
        if self.id != other.id:
            return False
        for k, v in self.data.items():
            if k not in other or other.data[k] != v:
                return False
        return True

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return f"Session(id={repr(self.id)},data={repr(self.data)})"


def unpack_hook(obj):
    if obj.get("type") == "session":
        return Session(obj["data"], obj["id"])
    return obj


def pack_hook(obj):
    if isinstance(obj, Session):
        return obj.dump()
    return obj


if __name__ == "__main__":
    s1 = Session()
    s1["c"] = 3
    s1.update({"d": 4, "e": 5})
    packed = msgpack.packb(s1, default=pack_hook, use_bin_type=True)
    s2 = msgpack.unpackb(packed, object_hook=unpack_hook, raw=False)
    s2.update({"a": 1, "b": 2})
    assert s2 == s2
    assert s2 != s1
    s2.pop("a")
    s2.pop("b")
    assert s2 == s1
    print(1, repr(s1))
    print(2, repr(s2))
    assert Session({"a": 1}) != Session({"a": 1})
    assert Session({"a": 1}) != Session({"b": 2})
    assert not Session()
    assert Session({1: 2})
