import json
from functools import wraps
from traceback import format_exc

from flask import redirect, session, url_for, request, make_response, g

import db
from utils import new_id


def auth_required(f):
    @wraps(f)
    def protected(*args, **kwargs):
        if not 'user' in session:
            return redirect(url_for("login", next=request.full_path))
        else:
            return f(*args, **kwargs)

    return protected


def csrf_protect(f):
    @wraps(f)
    def protected(*args, **kwargs):
        if request.method == "POST":
            saved_token = session.get("csrf_token")
            submitted_token = request.form.get("_csrf_token")
            if not saved_token or not submitted_token or saved_token != submitted_token:
                return redirect("/error")
        return f(*args, **kwargs)

    return protected


def api_endpoint(f):
    @wraps(f)
    def converted(*args, **kwargs):
        resp = make_response(json.dumps(f(*args, **kwargs), ensure_ascii=False))
        resp.headers["Content-Type"] = "application/json"
        return resp

    return converted


def api_exception(f):
    @wraps(f)
    def processed(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception:
            error_id = new_id(32)
            db.log("api_uncaught_exception", traceback=format_exc(), error_id=error_id)
            return {"status": 2, "error_id": error_id}

    return processed


def token_required(f):
    @wraps(f)
    def protected(*args, **kwargs):
        token = request.headers.get("X-Token")
        if token:
            user_id = db.token_to_user_id(token)
            if user_id:
                g.user_id = user_id
                return f(*args, **kwargs)
            else:
                db.log("invalid_token")
                return {"status": 4, "message": "会话已失效"}
        else:
            db.log("no_token")
            return {"status": 3, "message": "需要登录"}

    return protected
