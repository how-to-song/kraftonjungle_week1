import os
import uuid
import random
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from dotenv import load_dotenv
from flask import Flask, g, jsonify, make_response, redirect, render_template, request
from pymongo import MongoClient
from werkzeug.security import check_password_hash, generate_password_hash
from bson import ObjectId

load_dotenv()
client = MongoClient(os.environ["MONGO_URI"])
db = client["findjunglerdb"]
users = db["users"]

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
                options={"require": ["sub", "iat", "exp"]},
            )
            g.user_id = payload["sub"]
        except jwt.InvalidTokenError:
            response = make_response(redirect("/login"))
            response.delete_cookie("access_token", path="/")
            return response

        return view_function(*args, **kwargs)

    return wrapped_view


def create_auth_response(user_id):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
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
        max_age=8 * 60 * 60,
        httponly=True,
        samesite="Lax",
        secure=False,
        path="/",
    )
    return response


@app.route("/")
@login_required
def root():
    return redirect("/game")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            return render_template(
                "login.html",
                error_message="아이디 또는 비밀번호가 올바르지 않습니다.",
            )

        user = db["users"].find_one({"username": username})

        if user is None:
            return render_template(
                "login.html",
                error_message="아이디 또는 비밀번호가 올바르지 않습니다.",
            )

        stored_password_hash = user.get("password_hash")

        if not stored_password_hash or not check_password_hash(
            stored_password_hash, password
        ):
            return render_template(
                "login.html",
                error_message="아이디 또는 비밀번호가 올바르지 않습니다.",
            )

        return create_auth_response(user["_id"])

    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    response = make_response(redirect("/login"))
    response.delete_cookie("access_token", path="/")
    return response

@app.route("/game")
@login_required
def startgame():
    return render_template("start.html")
    
game_states = {}
    
@app.route("/game/play")
@login_required
def loadgame():
    answers = list(
        users.aggregate([
            {"$match": {"_id": {"$ne": ObjectId(g.user_id)}}}, 
            {"$sample": {"size": 5}}
            ])
    )
    
    wrongs = list(users.aggregate([
        {"$match": {"_id": {"$nin": [ObjectId(g.user_id), answers[0]["_id"]]}}},
        {"$sample": {"size": 4}},
    ]))
    
    candidates = [answers[0]] + wrongs
    random.shuffle(candidates)
    
    game_states[g.user_id] = {
        "answers": answers,
        "q_index": 0,
        "set_score": 0,
        "candidates": candidates,
        "wrong_count": 0,
        "revealed_hints": 1,
        "disabled": [],
        "solved": False,
    }
    
    return render_template("play.html",
                           candidates=candidates,
                           hints=answers[0]["features"][:1],
                           revealed_hints=1,
                           q_number=game_states[g.user_id]["q_index"] + 1
                           )
    

@app.route("/api/game/play/guess", methods=["POST"])
@login_required
def guess():
    selected_id = request.form.get("candidate_id")
    state = game_states[g.user_id]
    answer = state["answers"][state["q_index"]]
    if str(answer["_id"]) == selected_id:
        state["solved"] = True
        state["revealed_hints"] = 4
    else:
        state["disabled"].append(selected_id)
        state["wrong_count"] += 1
                
        if state["wrong_count"] == 4:
            state["solved"] = True
            state["revealed_hints"] = 4
        else:
            state["revealed_hints"] += 1
        
    if state["solved"]:
        score = 100 - 20 * state["wrong_count"]
        state["set_score"] += score
                    
    is_correct = str(answer["_id"]) == selected_id
    return jsonify({
        "result": "correct" if is_correct else "wrong",
        "solved":state["solved"],
        "score": score if state["solved"] else None,
        "revealed_hints": state["revealed_hints"],
        "hints": answer["features"][:state["revealed_hints"]],
        "disabled": state["disabled"],
        "answer_id": str(answer["_id"]) if state["solved"] else None
    })

@app.route("/api/game/next", methods=["POST"])
@login_required
def next_question():
    state = game_states[g.user_id]
    state["q_index"] += 1

    if state["q_index"] >= 5:
        users.update_one(
            {"_id": ObjectId(g.user_id)},
            {"$inc": {"total_score": state["set_score"]}}
        )
        del game_states[g.user_id]
        return redirect("/ranking")

    answer = state["answers"][state["q_index"]]
    wrongs = list(users.aggregate([
        {"$match": {"_id": {"$nin": [ObjectId(g.user_id), answer["_id"]]}}},
        {"$sample": {"size": 4}},
    ]))

    candidates = [answer] + wrongs
    random.shuffle(candidates)

    state["candidates"] = candidates
    state["wrong_count"] = 0
    state["revealed_hints"] = 1
    state["disabled"] = []
    state["solved"] = False

    return render_template("play.html",
                           candidates=candidates,
                           hints=answer["features"][:1],
                           revealed_hints=1,
                           q_number=state["q_index"] + 1
                           )


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not (4 <= len(username) <= 20):
            return render_template(
                "signup.html", error_message="아이디는 4~20자 입니다."
            )
        if not (username.isascii() and username.isalnum()):
            return render_template(
                "signup.html", error_message="아이디는 영문과 숫자만 가능합니다."
            )
        if users.find_one({"username": username}):
            return render_template(
                "signup.html", error_message="이미 사용중인 아이디입니다."
            )

        password = request.form.get("password", "").strip()
        if len(password) < 8:
            return render_template(
                "signup.html", error_message="비밀번호는 8자 이상 입니다."
            )

        password_confirm = request.form.get("password_confirm", "").strip()
        if password != password_confirm:
            return render_template("signup.html", error_message="비밀번호가 다릅니다.")

        photo = request.files.get("profile_image")
        if photo is None or photo.filename == "":
            return render_template(
                "signup.html", error_message="프로필 사진은 필수입니다."
            )
        ext = photo.filename.rsplit(".", 1)[-1].lower()
        if ext not in ["jpg", "jpeg", "png"]:
            return render_template(
                "signup.html", error_message=".jpg, .jpeg, .png만 가능합니다."
            )
        photo.seek(0, 2)
        size = photo.tell()
        photo.seek(0)
        if size > 5 * 1024 * 1024:
            return render_template(
                "signup.html", error_message="사진은 5MB 이하만 가능합니다."
            )

        name = request.form.get("name", "").strip()
        if name == "":
            return render_template(
                "signup.html", error_message="이름을 꼭 넣어야합니다."
            )

        features = [request.form.get(f"feature{i}", "").strip() for i in range(1, 5)]
        for feature in features:
            if not (2 <= len(feature) <= 30):
                return render_template(
                    "signup.html", error_message="특징은 2~30자 입니다."
                )
            if normalize(name) in normalize(feature):
                return render_template(
                    "signup.html", error_message="특징에는 이름을 넣을 수 없습니다."
                )

        filename = f"{uuid.uuid4().hex}.{ext}"
        save_path = os.path.join("static", "uploads", filename)
        os.makedirs("static/uploads", exist_ok=True)
        photo.save(save_path)

        image_path = f"/static/uploads/{filename}"

        now = datetime.now(timezone.utc)
        password_hash = generate_password_hash(password)

        result = users.insert_one(
            {
                "username": username,
                "password_hash": password_hash,
                "name": name,
                "features": features,
                "profile_image": image_path,
                "total_score": 0,
                "created_at": now,
                "updated_at": now,
            }
        )
        return create_auth_response(result.inserted_id)

    return render_template("signup.html")


@app.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    edit_user = users.find_one({"_id": ObjectId(g.user_id)})

    if request.method == "POST":
        photo = request.files.get("profile_image")
        if photo and photo.filename:
            ext = photo.filename.rsplit(".", 1)[-1].lower()
            if ext not in ["jpg", "jpeg", "png"]:
                return render_template(
                    "edit.html",
                    error_message=".jpg, .jpeg, .png만 가능합니다.",
                    edit_user=edit_user,
                )
            photo.seek(0, 2)
            size = photo.tell()
            photo.seek(0)
            if size > 5 * 1024 * 1024:
                return render_template(
                    "edit.html",
                    error_message="사진은 5MB 이하만 가능합니다.",
                    edit_user=edit_user,
                )
            filename = f"{uuid.uuid4().hex}.{ext}"
            save_path = os.path.join("static", "uploads", filename)
            os.makedirs("static/uploads", exist_ok=True)
            photo.save(save_path)

            image_path = f"/static/uploads/{filename}"

        name = request.form.get("name", "").strip()
        if name == "":
            return render_template(
                "edit.html",
                error_message="이름을 꼭 넣어야합니다.",
                edit_user=edit_user,
            )

        features = [request.form.get(f"feature{i}", "").strip() for i in range(1, 5)]
        for feature in features:
            if not (2 <= len(feature) <= 30):
                return render_template(
                    "edit.html",
                    error_message="특징은 2~30자 입니다.",
                    edit_user=edit_user,
                )
            if normalize(name) in normalize(feature):
                return render_template(
                    "edit.html",
                    error_message="특징에는 이름을 넣을 수 없습니다.",
                    edit_user=edit_user,
                )

        now = datetime.now(timezone.utc)

        set_data = {
            "name": name,
            "features": features,
            "updated_at": now,
        }
        if photo and photo.filename:
            set_data["profile_image"] = image_path

        users.update_one({"_id": edit_user["_id"]}, {"$set": set_data})

        return redirect("/game")

    return render_template("edit.html", edit_user=edit_user)


@app.route("/ranking", methods=["GET"])
@login_required
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
