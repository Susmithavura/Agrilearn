import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from app import create_app  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402


class ApiSecurityTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-key-not-for-production-123456789",
            "FRONTEND_ORIGIN": "http://127.0.0.1:8000",
            "DB_CONFIG": {},
        })
        self.client = self.app.test_client()

    def test_health_is_public(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["status"], "ok")

    def test_dashboard_requires_login(self):
        response = self.client.get("/api/dashboard/admin")
        self.assertEqual(response.status_code, 401)

    def test_role_is_loaded_from_database_not_login_payload(self):
        account = {
            "id": 17,
            "full_name": "Actual Administrator",
            "username": "real-admin",
            "password_hash": generate_password_hash("correct-horse-battery-staple"),
            "role": "admin",
            "email": None,
            "phone": None,
            "account_status": "active",
            "language_preference": "en",
        }
        csrf = self.client.get("/api/auth/csrf").get_json()["data"]["csrf_token"]
        with patch("app.routes.auth.fetch_one", return_value=account):
            response = self.client.post(
                "/api/auth/login",
                json={
                    "username": "real-admin",
                    "password": "correct-horse-battery-staple",
                    "role": "farmer",
                },
                headers={"X-CSRF-Token": csrf},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["user"]["role"], "admin")

    def test_inactive_account_cannot_login(self):
        account = {
            "id": 18,
            "full_name": "Inactive User",
            "username": "inactive",
            "password_hash": generate_password_hash("correct-horse-battery-staple"),
            "role": "farmer",
            "email": None,
            "phone": None,
            "account_status": "inactive",
            "language_preference": "en",
        }
        csrf = self.client.get("/api/auth/csrf").get_json()["data"]["csrf_token"]
        with patch("app.routes.auth.fetch_one", return_value=account):
            response = self.client.post(
                "/api/auth/login",
                json={"username": "inactive", "password": "correct-horse-battery-staple"},
                headers={"X-CSRF-Token": csrf},
            )
        self.assertEqual(response.status_code, 401)

    def test_incorrect_password_is_rejected(self):
        account = {
            "id": 20,
            "full_name": "Test Farmer",
            "username": "test-farmer",
            "password_hash": generate_password_hash("correct-horse-battery-staple"),
            "role": "farmer",
            "email": None,
            "phone": None,
            "account_status": "active",
            "language_preference": "en",
        }
        csrf = self.client.get("/api/auth/csrf").get_json()["data"]["csrf_token"]
        with patch("app.routes.auth.fetch_one", return_value=account):
            response = self.client.post(
                "/api/auth/login",
                json={"username": "test-farmer", "password": "incorrect-password"},
                headers={"X-CSRF-Token": csrf},
            )
        self.assertEqual(response.status_code, 401)

    def test_role_guard_rejects_non_admin(self):
        with self.client.session_transaction() as browser_session:
            browser_session["user_id"] = 19
        coordinator = {
            "id": 19,
            "full_name": "Coordinator",
            "username": "coordinator",
            "role": "coordinator",
            "account_status": "active",
        }
        with patch("app.database.fetch_one", return_value=coordinator):
            response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 403)

    def test_farmer_cannot_create_accounts(self):
        with self.client.session_transaction() as browser_session:
            browser_session["user_id"] = 21
            browser_session["csrf_token"] = "valid-csrf-token"
        farmer = {
            "id": 21,
            "full_name": "Farmer",
            "username": "farmer",
            "role": "farmer",
            "account_status": "active",
        }
        with patch("app.database.fetch_one", return_value=farmer):
            response = self.client.post(
                "/api/users",
                json={"full_name": "Unauthorized", "role": "admin"},
                headers={"X-CSRF-Token": "valid-csrf-token"},
            )
        self.assertEqual(response.status_code, 403)

    def test_state_changes_require_csrf(self):
        response = self.client.post("/api/auth/login", json={"username": "x", "password": "x"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"]["code"], "csrf_failed")

    def test_login_csrf_bootstrap_token_reaches_authentication_check(self):
        csrf = self.client.get("/api/auth/csrf").get_json()["data"]["csrf_token"]
        with patch("app.routes.auth.fetch_one", return_value=None):
            response = self.client.post(
                "/api/auth/login",
                json={"username": "missing-account", "password": "not-a-real-password"},
                headers={"X-CSRF-Token": csrf},
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"]["code"], "invalid_credentials")

    def test_login_rejects_a_csrf_token_from_another_session(self):
        self.client.get("/api/auth/csrf")
        response = self.client.post(
            "/api/auth/login",
            json={"username": "missing-account", "password": "not-a-real-password"},
            headers={"X-CSRF-Token": "token-from-another-session"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"]["code"], "csrf_failed")

    def test_csrf_bootstrap_uses_http_only_same_site_cookie(self):
        response = self.client.get("/api/auth/csrf")
        self.assertEqual(response.status_code, 200)
        cookie = response.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_https_cross_site_cookie_policy_can_be_configured(self):
        app = create_app({
            "TESTING": True,
            "SECRET_KEY": "cookie-policy-test-secret-key-123456789",
            "SESSION_COOKIE_SECURE": True,
            "SESSION_COOKIE_SAMESITE": "None",
        })
        response = app.test_client().get("/api/auth/csrf")
        cookie = response.headers["Set-Cookie"]
        self.assertIn("Secure", cookie)
        self.assertIn("SameSite=None", cookie)

    def test_cors_allows_only_the_configured_origin_with_credentials(self):
        response = self.client.get(
            "/api/health",
            headers={"Origin": "http://127.0.0.1:8000"},
        )
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "http://127.0.0.1:8000")
        self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")

        rejected = self.client.get(
            "/api/health",
            headers={"Origin": "https://untrusted.example"},
        )
        self.assertIsNone(rejected.headers.get("Access-Control-Allow-Origin"))


if __name__ == "__main__":
    unittest.main()
