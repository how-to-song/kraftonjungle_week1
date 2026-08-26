import os
import uuid
import random
from datetime import datetime, timedelta, timezone
from functools import wraps


import jwt
from dotenv import load_dotenv
from flask import Flask, g, make_response, redirect, render_template, request
from pymongo import MongoClient
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
client = MongoClient(os.environ["MONGO_URI"])
db = client["findjunglerdb"]
users = db["users"]

app = Flask(__name__)





@app.route("/", methods=["GET", "POST"])

def loadgame():
    random_users = list(
        users.aggregate([
            {"$sample": {"size": 5}}, ])
    )
    answer = random.randint(1, 5)
    answer_user = random_users[answer - 1]

    if request.method == "POST":
        return redirect("/")


    return render_template(
        "index.html",
        players=random_users,
        answer=answer,
        hints=answer_user["features"]
    )

 



@app.route("/game", methods=["GET", "POST"])

def loadgame():
    random_users = list(
        users.aggregate([
            {"$sample": {"size": 5}}, ])
    )
    answer = random.randint(1, 5)
    answer_user = random_users[answer - 1]

    if request.method == "POST":
        return redirect("/game")


    return render_template(
        "game.html",
        players=random_users,
        answer=answer,
        hints=answer_user["features"]
    )

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
    return render_template("index.html")

@app.route("/logout", methods=["POST"])
def logout():
    response = make_response(redirect("/login"))
    response.delete_cookie("access_token", path="/")
    return response

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not (4 <= len(username) <= 20):
            return render_template("signup.html", error_message="아이디는 4~20자 입니다.")
        if not (username.isascii() and username.isalnum()):
            return render_template("signup.html", error_message="아이디는 영문과 숫자만 가능합니다.")
        if users.find_one({"username": username}):
            return render_template("signup.html", error_message="이미 사용중인 아이디입니다.")


        password = request.form.get("password", "").strip()
        if (len(password) < 8):
            return render_template("signup.html", error_message="비밀번호는 8자 이상 입니다.")

        password_confirm = request.form.get("password_confirm", "").strip()
        if (password != password_confirm):
            return render_template("signup.html", error_message="비밀번호가 다릅니다.")

        photo = request.files.get("profile_image")
        if photo is None or photo.filename == "":
            return render_template("signup.html", error_message="프로필 사진은 필수입니다.")
        ext = photo.filename.rsplit(".", 1)[-1].lower()
        if ext not in ["jpg", "jpeg", "png"]:
            return render_template("signup.html", error_message=".jpg, .jpeg, .png만 가능합니다.")
        photo.seek(0, 2)
        size = photo.tell()
        photo.seek(0)
        if (size > 5 * 1024 * 1024):
            return render_template("signup.html", error_message="사진은 5MB 이하만 가능합니다.")

        name = request.form.get("name", "").strip()
        if (name == ""):
            return render_template("signup.html", error_message="이름을 꼭 넣어야합니다.")

        features = [request.form.get(f"feature{i}", "").strip() for i in range(1, 5)]
        for feature in features:
            if not (2 <= len(feature) <= 30):
                return render_template("signup.html", error_message="특징은 2~30자 입니다.")
            if normalize(name) in normalize(feature):
                return render_template("signup.html", error_message="특징에는 이름을 넣을 수 없습니다.")

        filename = f"{uuid.uuid4().hex}.{ext}"
        save_path = os.path.join("static","uploads", filename)
        os.makedirs("static/uploads", exist_ok=True)
        photo.save(save_path)

        image_path = f"/static/uploads/{filename}"


        now = datetime.now(timezone.utc)
        password_hash = generate_password_hash(password)
        result = users.insert_one({
            "username": username,
            "password_hash": password_hash,
            "name":name,
            "features": features,
            "profile_image": image_path,
            "total_score": 0,
            "created_at": now,
            "updated_at":now,
        })
        return "가입 성공!"


    return render_template("signup.html")

@app.route("/edit", methods=["GET", "POST"])
def edit():
    edit_user = users.find_one({"username": "song03621"})

    if request.method == "POST":
        photo = request.files.get("profile_image")
        if photo and photo.filename:
            ext = photo.filename.rsplit(".", 1)[-1].lower()
            if ext not in ["jpg", "jpeg", "png"]:
                return render_template("edit.html", error_message=".jpg, .jpeg, .png만 가능합니다.", edit_user=edit_user)
            photo.seek(0, 2)
            size = photo.tell()
            photo.seek(0)
            if (size > 5 * 1024 * 1024):
                return render_template("edit.html", error_message="사진은 5MB 이하만 가능합니다.", edit_user=edit_user)
            filename = f"{uuid.uuid4().hex}.{ext}"
            save_path = os.path.join("static","uploads", filename)
            os.makedirs("static/uploads", exist_ok=True)
            photo.save(save_path)

            image_path = f"/static/uploads/{filename}"

        name = request.form.get("name", "").strip()
        if (name == ""):
            return render_template("edit.html", error_message="이름을 꼭 넣어야합니다.", edit_user=edit_user)

        features = [request.form.get(f"feature{i}", "").strip() for i in range(1, 5)]
        for feature in features:
            if not (2 <= len(feature) <= 30):
                return render_template("edit.html", error_message="특징은 2~30자 입니다.", edit_user=edit_user)
            if normalize(name) in normalize(feature):
                return render_template("edit.html", error_message="특징에는 이름을 넣을 수 없습니다.", edit_user=edit_user)




        now = datetime.now(timezone.utc)

        set_data = {
            "name": name,
            "features": features,
            "updated_at": now,
        }
        if photo and photo.filename:
            set_data["profile_image"] = image_path

        users.update_one(
            {"_id": edit_user["_id"]},
            {"$set": set_data}
        )

        return "수정 성공!"


    return render_template("edit.html", edit_user=edit_user)

@app.route("/ranking", methods=["GET"])
def ranking():
    ranked = list(users.find({"total_score": {"$gt": 0}}).sort("total_score", -1))
    
    prev_score = None
    prev_rank = 0
    for entry in ranked:
        if entry["total_score"] == prev_score:
            rank = prev_rank
        else:
            rank = prev_rank + 1
        entry["rank"] = rank
        prev_rank = rank
        prev_score = entry["total_score"]
        
    max_score = ranked[0]["total_score"] if ranked else 1
        
    
    return render_template("ranking.html", ranking_entries=ranked, max_score=max_score)

def normalize(s):
    return s.replace(" ", "").lower()

if __name__ == "__main__":
    app.run(debug=True)