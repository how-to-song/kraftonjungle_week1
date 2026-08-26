import unittest
from app import app, users
import os
import jwt
from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import patch

from bson import ObjectId
from pymongo.results import InsertOneResult


class LoginPageTest(unittest.TestCase):
    def test_get_login_returns_200(self):
        response = app.test_client().get("/login")
        self.assertEqual(response.status_code, 200)

    def test_get_login_shows_login_heading(self):
        response = app.test_client().get("/login")
        html = response.get_data(as_text=True)
        self.assertIn("로그인", html)

    def test_get_login_shows_username_field(self):
        response = app.test_client().get("/login")
        html = response.get_data(as_text=True)
        self.assertIn('name="username"', html)

    def test_get_login_shows_password_field(self):
        response = app.test_client().get("/login")
        html = response.get_data(as_text=True)
        self.assertIn('name="password"', html)
        self.assertIn('type="password"', html)

    def test_post_login_with_missing_fields_shows_error(self):
        response = app.test_client().post("/login", data={})
        self.assertEqual(response.status_code, 200)

        html = response.get_data(as_text=True)
        self.assertIn("아이디 또는 비밀번호가 올바르지 않습니다.", html)

    def test_post_login_with_unknown_user_shows_same_error(self):
        response = app.test_client().post(
            "/login",
            data={
                "username": "no_such_user_84721",
                "password": "wrongpassword",
            },
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("아이디 또는 비밀번호가 올바르지 않습니다.", html)

    def test_post_login_with_valid_credentials_redirects_to_game(self):
        response = app.test_client().post(
            "/login",
            data={
                "username": "song03621",
                "password": "testpassword123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/game")
        self.assertIn(
            "access_token=",
            response.headers.get("Set-Cookie", ""),
        )

    def test_get_game_without_token_redirects_to_login(self):
        response = app.test_client().get("/game")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

    def test_get_game_with_valid_login_cookie_returns_200(self):
        client = app.test_client()

        client.post(
            "/login",
            data={
                "username": "song03621",
                "password": "testpassword123",
            },
        )

        response = client.get("/game")

        self.assertEqual(response.status_code, 200)
        self.assertIn("정글러 맞추기", response.get_data(as_text=True))

    def test_get_game_with_invalid_token_redirects_to_login(self):
        client = app.test_client()
        client.set_cookie("access_token", "forged-token")

        response = client.get("/game")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")
        set_cookie_header = response.headers.get("Set-Cookie", "")
        self.assertIn("access_token=;", set_cookie_header)
        self.assertIn("Max-Age=0", set_cookie_header)

    def test_logout_clears_access_token_cookie(self):
        client = app.test_client()

        client.post(
            "/login",
            data={
                "username": "song03621",
                "password": "testpassword123",
            },
        )

        logout_response = client.post("/logout")
        game_response = client.get("/game")

        self.assertEqual(logout_response.status_code, 302)
        self.assertEqual(logout_response.headers["Location"], "/login")
        self.assertEqual(game_response.status_code, 302)
        self.assertEqual(game_response.headers["Location"], "/login")

    def test_get_game_with_expired_token_redirects_to_login(self):
        client = app.test_client()
        now = datetime.now(timezone.utc)
        expired_at = now - timedelta(hours=1)
        payload = {
            "sub": "test-user-id",
            "iat": now - timedelta(hours=2),
            "exp": expired_at,
        }
        expired_token = jwt.encode(
            payload,
            os.environ["JWT_SECRET_KEY"],
            algorithm="HS256",
        )

        client.set_cookie("access_token", expired_token)
        response = client.get("/game")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

        set_cookie_header = response.headers.get("Set-Cookie", "")
        self.assertIn("access_token=;", set_cookie_header)
        self.assertIn("Max-Age=0", set_cookie_header)

    def test_get_edit_without_token_redirects_to_login(self):
        client = app.test_client()
        response = client.get("/edit")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

    def test_get_ranking_without_token_redirects_to_login(self):
        client = app.test_client()
        response = client.get("/ranking")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

    def test_post_signup_with_valid_data_sets_cookie_and_redirects_to_game(self):
        client = app.test_client()
        new_user_id = ObjectId()
        insert_result = InsertOneResult(new_user_id, acknowledged=True)
        with (
            patch.object(users, "find_one", return_value=None),
            patch.object(users, "insert_one", return_value=insert_result),
            patch("werkzeug.datastructures.FileStorage.save"),
        ):
            response = client.post(
                "/signup",
                data={
                    "username": "signupautotest",
                    "password": "testpassword123",
                    "password_confirm": "testpassword123",
                    "name": "테스트사용자",
                    "feature1": "밝은 성격",
                    "feature2": "운동 좋아함",
                    "feature3": "커피 좋아함",
                    "feature4": "게임 좋아함",
                    "profile_image": (BytesIO(b"fake-image"), "profile.png"),
                },
                content_type="multipart/form-data",
            )

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], "/game")
            self.assertIn(
                "access_token=",
                response.headers.get("Set-Cookie", ""),
            )

            cookie = client.get_cookie("access_token")
            decoded_payload = jwt.decode(
                cookie.value,
                os.environ["JWT_SECRET_KEY"],
                algorithms=["HS256"],
            )
            self.assertEqual(decoded_payload["sub"], str(new_user_id))
            self.assertEqual(
                set(decoded_payload.keys()),
                {"sub", "iat", "exp"},
            )

    def test_get_signup_returns_200(self):
        response = app.test_client().get("/signup")
        self.assertEqual(response.status_code, 200)

    def test_get_edit_with_valid_login_cookie_shows_current_user(self):
        client = app.test_client()

        client.post(
            "/login",
            data={
                "username": "song03621",
                "password": "testpassword123",
            },
        )

        response = client.get("/edit")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("song03621", html)

    def test_get_root_without_token_redirects_to_login(self):
        client = app.test_client()
        response = client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

    def test_get_root_with_valid_login_cookie_redirects_to_game(self):
        client = app.test_client()
        client.post(
            "/login",
            data={
                "username": "song03621",
                "password": "testpassword123",
            },
        )
        response = client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/game")

    def test_get_game_with_token_missing_exp_redirects_to_login(self):
        client = app.test_client()
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "test-user-id",
            "iat": now,
        }
        token_without_exp = jwt.encode(
            payload,
            os.environ["JWT_SECRET_KEY"],
            algorithm="HS256",
        )

        client.set_cookie("access_token", token_without_exp)
        response = client.get("/game")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

        set_cookie_header = response.headers.get("Set-Cookie", "")
        self.assertIn("access_token=;", set_cookie_header)
        self.assertIn("Max-Age=0", set_cookie_header)

    def test_get_login_shows_signup_link(self):
        response = app.test_client().get("/login")
        html = response.get_data(as_text=True)
        self.assertIn('href="/signup"', html)

    def test_get_ranking_with_valid_login_shows_logout_form(self):
        client = app.test_client()
        client.post(
            "/login",
            data={
                "username": "song03621",
                "password": "testpassword123",
            },
        )
        response = client.get("/ranking")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('action="/logout"', html)
        self.assertIn('method="post"', html)
        self.assertIn("로그아웃", html)


if __name__ == "__main__":
    unittest.main()
