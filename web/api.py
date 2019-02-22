from base64 import b64decode

from flask import Blueprint, request, g

import db
from decorators import api_endpoint, api_exception, token_required
from utils import AppError

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/login", methods=("POST",))
@api_endpoint
@api_exception
def api_login():
    try:
        req = request.json
        if "username" not in req or "password" not in req:
            raise AppError("无效请求")
        user = db.check_password(req["username"], req["password"])
        return {"status": 0, "token": db.get_token(user["id"])}
    except AppError as e:
        return {"status": 1, "message": e.message}


@bp.route("/messages", methods=("POST",))
@api_endpoint
@api_exception
@token_required
def api_messages():
    req = request.json
    return {"status": 0, "messages": db.get_messages(g.token["user_id"], req.get("date", ""))}


@bp.route("/api/submit", methods=("POST",))
@api_endpoint
@api_exception
@token_required
def api_submit():
    data = b64decode(request.json.get("data", ""))
    db.new_parse_task(g.token["user_id"], data)
    return {"status": 0}


@bp.route("/api/dates", methods=("POST",))
@api_endpoint
@api_exception
@token_required
def api_dates():
    return {"status": 0, "dates": db.get_dates(g.token["user_id"])}
