import os
import jwt
from dotenv import load_dotenv
from pymongo import MongoClient
from flask import Flask, render_template, request, make_response, redirect, g
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta, timezone
from functools import wraps

load_dotenv()
client = MongoClient(os.environ["MONGO_URI"])
db = client["findjunglerdb"]
app = Flask(__name__)

def login_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        access_token = request.cookies.get("access_token")

        if not access_token:
            return redirect("/login")

        try:
            payload = jwt.decode(
                access_token,
                os.environ["JWT_SECRET_KEY"],
                algorithms=["HS256"],
            )
            g.user_id = payload["sub"]
        except jwt.InvalidTokenError:
            return redirect("/login")

        return view_function(*args, **kwargs)

    return wrapped_view

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            return render_template("login.html", error_message="아이디 또는 비밀번호가 올바르지 않습니다.",)

        user = db["users"].find_one({"username": username})

        if user is None:
            return render_template(
                "login.html", error_message = "아이디 또는 비밀번호가 올바르지 않습니다.",)

        stored_password_hash = user.get("password_hash")

        if not stored_password_hash or not check_password_hash(
            stored_password_hash, password):
            return render_template(
                "login.html", error_message = "아이디 또는 비밀번호가 올바르지 않습니다.",)

        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user["_id"]),
            "iat": now,
            "exp": now + timedelta(hours=8),
        }

        access_token = jwt.encode(
            payload,
            os.environ["JWT_SECRET_KEY"],
            algorithm="HS256",
        )

        response = make_response(redirect("/game"))
        response.set_cookie(
            "access_token",
            access_token,
            max_age= 8 * 60 * 60,
            httponly = True,
            samesite="Lax",
            secure=False,
            path="/",
        )
        return response

    return render_template("login.html")
@app.route("/game")
@login_required
def game():
    return "게임 페이지"

@app.route("/logout", methods=["POST"])
def logout():
    response = make_response(redirect("/login"))
    response.delete_cookie("access_token", path="/")
    return response