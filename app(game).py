import os
import uuid
import certifi
from datetime import datetime, timedelta, timezone
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, g, make_response, redirect, render_template, request, session, url_for
from pymongo import MongoClient
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
client = MongoClient(
    os.environ["MONGO_URI"],
    tlsCAFile=certifi.where()
)
db = client["findjunglerdb"]
users = db["users"]

app = Flask(__name__)

import random





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

 



if __name__ == "__main__":
    app.run(debug=True, port=5001)