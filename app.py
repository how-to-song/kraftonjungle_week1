import os, uuid
from dotenv import load_dotenv
from pymongo import MongoClient
from flask import Flask, render_template, request

from datetime import datetime, timezone

load_dotenv()
client = MongoClient(os.environ["MONGO_URI"])
db = client["findjunglerdb"]
users = db["users"]


app = Flask(__name__)

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
        
        result = users.insert_one({
            "username": username,
            "password_hash": "TODO_HASH",
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



# DB 연결 확인 코드
# 1) 연결 확인 (ping)
#print(client.admin.command("ping"))    # {'ok': 1.0} 나오면 연결 성공

# 2) 쓰기 → 읽기 왕복 테스트
#db = client["mbti"]
#db["test"].insert_one({"hello": "world"})
#print(db["test"].find_one())           # 방금 넣은 문서가 출력되면 OK

# 3) 뒷정리 (테스트 데이터 삭제)
#db["test"].drop()
