import unittest
from app import app

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
        self.assertIn('name="username"',html)

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
        response = app.test_client().post("/login", data={
            "username": "no_such_user_84721", "password": "wrongpassword",},)
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
        self.assertIn("access_token=", response.headers.get("Set-Cookie", ""),
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
        self.assertIn("게임 페이지", response.get_data(as_text=True))

    def test_get_game_with_invalid_token_redirects_to_login(self):
        client = app.test_client()
        client.set_cookie("access_token", "forged-token")

        response = client.get("/game")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

    def test_logout_clears_access_token_cookie(self):
        client = app.test_client()

        client.post(
            "/login",
            data = {
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

if __name__ == "__main__":
    unittest.main()
