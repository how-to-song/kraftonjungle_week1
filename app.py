import os
from dotenv import load_dotenv
from pymongo import MongoClient
from flask import Flask, render_template, request

load_dotenv()
client = MongoClient(os.environ["MONGO_URI"])

app = Flask(__name__)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not (4 <= len(username) <= 20):
            return render_template("signup.html", error_message="아이디는 4~20자 입니다.")
        
        password = request.form.get("password", "").strip()
        if (len(password) < 8):
            return render_template("signup.html", error_message="비밀번호는 8자 이상 입니다.")
        
        password_confirm = request.form.get("password_confirm", "").strip()
        if (password != password_confirm):
            return render_template("signup.html", error_message="비밀번호가 다릅니다.")
        
        photo = request.files.get("profile_image")
        if photo is None or photo.filename == "":
            return render_template("signup.html", error_message="프로필 사진은 필수입니다.")
        
        name = request.form.get("name", "").strip()
        if (name == ""):
            return render_template("signup.html", error_message="이름을 꼭 넣어야합니다.")
        
        features = [request.form.get(f"feature{i}", "").strip() for i in range(1, 5)]
        for feature in features:
            if not (2 <= len(feature) <= 30):
                return render_template("signup.html", error_message="특징은 2~30자 입니다.")
            if normalize(name) in normalize(feature):
                return render_template("signup.html", error_message="특징에는 이름을 넣을 수 없습니다.")
            
    return render_template("signup.html")

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
