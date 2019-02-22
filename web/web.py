from datetime import datetime
from json import load
from os.path import join, dirname
from re import fullmatch

from flask import Flask, render_template, request, redirect, session, url_for, abort
from redis import Redis

import db
from api import bp
from decorators import auth_required, csrf_protect
from sessions import RedisSessionManager
from utils import new_id, connect_db, AppError

app = Flask(__name__)
app.register_blueprint(bp)


def get_csrf_token():
    if "csrf_token" not in session:
        token = new_id()
        session["csrf_token"] = token
    else:
        token = session["csrf_token"]
    return token


def require_fields(*fields):
    if not all([key in request.form for key in fields]):
        return False
    if not all([request.form[key] for key in fields]):
        return False
    return True


def csrf_field():
    return f'<input name="_csrf_token" type="hidden" value="{get_csrf_token()}">'


@app.route('/')
def index():
    return render_template("index.html")


@app.route('/view')
@auth_required
def view():
    return render_template("view.html", dates=db.get_dates(session["user"]["id"]))


@app.route('/view/<date>')
@auth_required
def messages(date):
    if not fullmatch("\d{4}-\d{2}-\d{2}", date):
        abort(404)
    messages = db.get_messages(session["user"]["id"], date)
    grouped_messages = {}
    for message in messages:
        message["author"]=message["author"][0]+"*"*2
        group_name = message["group"]
        if not group_name in grouped_messages:
            grouped_messages[group_name] = []
        grouped_messages[group_name].append(message)
    prev_date, next_date = db.get_surrounding_days(session["user"]["id"], date)
    return render_template("messsages.html", messages=grouped_messages, prev_date=prev_date, next_date=next_date, date=date)


@app.route('/login', methods=("GET", "POST"))
@csrf_protect
def login():
    if request.method == "GET":
        return render_template("login.html", url=url_for("login", next=request.args.get("next", "/")))
    else:
        try:
            if not require_fields("username", "password"):
                raise AppError("必填项未填")
            session["user"] = db.check_password(request.form["username"], request.form["password"])
            target = request.args.get("next", "/")
            return redirect(target)
        except AppError as e:
            db.log("login_failure", username=request.form.get("username"))
            return render_template("login.html", errors=(e.message,))


@app.route('/register', methods=("GET", "POST"))
@csrf_protect
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        try:
            if not require_fields("username", "password", "email"):
                raise AppError("必填项未填")
            db.new_user(request.form["email"], request.form["username"], request.form["password"])
            return redirect("/")
        except AppError as e:
            db.log("register_failure", username=request.form.get("username"), email=request.form.get("email"))
            return render_template("register.html", errors=(e.message,))


@app.route('/logout')
def logout():
    if "user" in session:
        session.pop("user")
    return redirect("/")


@app.route('/profile')
@auth_required
def profile():
    user = db.get_user(session["user"]["id"])
    register_time = datetime.fromtimestamp(user["registered_timestamp"])
    return render_template("profile.html", items=[("注册时间", str(register_time))])


@app.route('/edit/password', methods=("GET", "POST"))
@csrf_protect
@auth_required
def edit_password():
    if request.method == "GET":
        return render_template("edit-password.html")
    elif request.method == "POST":
        try:
            user_id = session["user"]["id"]
            if not require_fields("old_password", "new_password"):
                raise AppError("表单项未完全填写")
            old_password, new_password = request.form["old_password"], request.form["new_password"]
            if not db.recheck_password(user_id, old_password):
                raise AppError("原密码错误")
            db.change_password(user_id, new_password)
            session.pop("user")
            return render_template("edit-password.html", successes=("密码已成功修改，请重新登录",))
        except AppError as e:
            return render_template("edit-password.html", errors=(e.message,))


@app.route('/upload', methods=("GET", "POST"))
@csrf_protect
@auth_required
def upload():
    if request.method == "GET":
        return render_template("upload.html")
    else:
        try:
            file = request.files.get("file")
            if not file or not file.filename:
                raise AppError("未选择文件")
            db.new_parse_task(session["user"]["id"], file.read())
            return redirect("/")
        except AppError as e:
            return render_template("upload.html", errors=(e.message,))


@app.route("/search")
@auth_required
def search():
    if not all([x in request.args for x in ("keyword",)]) or len(request.args.get("keyword", "")) == 0:
        return render_template("search.html")
    keyword = request.args["keyword"]
    messages = list(db.search_messages(session["user"]["id"], {"author": {"$regex": f".*{keyword}.*"}}))
    return render_template("search.html", results=messages)


@app.route('/error')
def error():
    return "Error!"


@app.errorhandler(404)
def page_not_found(e):
    try:
        url = request.url
    except Exception:
        url = ""
    return render_template('404.html', url=url), 404


app.jinja_env.globals['csrf_field'] = csrf_field
with open(join(dirname(__file__), "../config.json")) as f:
    config = load(f)

redis = Redis()
db.init(connect_db(config), redis)
db.ensure_indexes()

app.secret_key = config["secret_key"]
app.session_cookie_name = "SESSION_ID"
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
app.session_interface = RedisSessionManager(redis)

if __name__ == "__main__":
    app.run("0.0.0.0", 10000, debug=True)
