import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from app.config import Config, mysql_tls_options, validate_production_mysql_tls  # noqa: E402


class ProductionConfigTests(unittest.TestCase):
    def production_config(self, **overrides):
        values = {
            "FLASK_ENV": "production",
            "FLASK_DEBUG": False,
            "FRONTEND_ORIGIN": "https://app.example.test",
            "SESSION_COOKIE_SECURE": True,
            "SESSION_COOKIE_SAMESITE": "Lax",
            "SESSION_LIFETIME_MINUTES": 60,
            "SECRET_KEY": "production-only-test-secret-at-least-32-characters",
            "DB_CONFIG": {
                "password": "test-db-password",
                "ssl_ca": "ca.pem",
                "ssl_verify_cert": True,
                "ssl_verify_identity": True,
            },
        }
        values.update(overrides)
        return patch.multiple(Config, **values)

    def test_production_configuration_accepts_https_and_verified_mysql_tls(self):
        with patch.dict(os.environ, {"DB_APP_ALLOWED_HOST": "10.20.30.40"}):
            with self.production_config():
                Config.validate()

    def test_production_requires_secure_cookies(self):
        with patch.dict(os.environ, {"DB_APP_ALLOWED_HOST": "10.20.30.40"}):
            with self.production_config(SESSION_COOKIE_SECURE=False):
                with self.assertRaisesRegex(RuntimeError, "SESSION_COOKIE_SECURE=true"):
                    Config.validate()

    def test_production_rejects_debug_mode(self):
        with patch.dict(os.environ, {"DB_APP_ALLOWED_HOST": "10.20.30.40", "FLASK_DEBUG": "1"}):
            with self.production_config(FLASK_DEBUG=True):
                with self.assertRaisesRegex(RuntimeError, "FLASK_DEBUG=0"):
                    Config.validate()

    def test_production_requires_exact_client_host_and_verified_mysql_tls(self):
        with patch.dict(os.environ, {"DB_APP_ALLOWED_HOST": "10.20.30.40"}):
            with self.production_config(DB_CONFIG={"password": "test-db-password"}):
                with self.assertRaisesRegex(RuntimeError, "Production MySQL requires"):
                    Config.validate()

    def test_production_requires_explicit_non_wildcard_client_host(self):
        with patch.dict(os.environ, {"FLASK_DEBUG": "0"}, clear=True):
            with self.production_config():
                with self.assertRaisesRegex(RuntimeError, "DB_APP_ALLOWED_HOST"):
                    Config.validate()
        with patch.dict(os.environ, {"DB_APP_ALLOWED_HOST": "%", "FLASK_DEBUG": "0"}):
            with self.production_config():
                with self.assertRaisesRegex(RuntimeError, "wildcards are not allowed"):
                    Config.validate()

    def test_production_requires_an_https_frontend_origin(self):
        with patch.dict(os.environ, {"DB_APP_ALLOWED_HOST": "10.20.30.40"}):
            with self.production_config(FRONTEND_ORIGIN="http://app.example.test"):
                with self.assertRaisesRegex(RuntimeError, "must use HTTPS"):
                    Config.validate()

    def test_frontend_origin_rejects_paths_and_multiple_origins(self):
        for origin in ("https://app.example.test/path", "https://app.example.test,https://other.example"):
            with self.subTest(origin=origin), patch.dict(os.environ, {"DB_APP_ALLOWED_HOST": "10.20.30.40"}):
                with self.production_config(FRONTEND_ORIGIN=origin):
                    with self.assertRaisesRegex(RuntimeError, "one exact HTTP"):
                        Config.validate()

    def test_mysql_tls_options_use_configured_ca_and_verification(self):
        with patch.dict(os.environ, {
            "DB_SSL_CA": "mysql-ca.pem",
            "DB_SSL_VERIFY_CERT": "true",
            "DB_SSL_VERIFY_IDENTITY": "true",
        }):
            self.assertEqual(mysql_tls_options(), {
                "ssl_ca": "mysql-ca.pem",
                "ssl_verify_cert": True,
                "ssl_verify_identity": True,
            })

    def test_production_database_setup_requires_verified_tls(self):
        with patch.dict(os.environ, {"FLASK_ENV": "production", "DB_SSL_CA": ""}):
            with self.assertRaisesRegex(RuntimeError, "Production MySQL requires"):
                validate_production_mysql_tls()
        with patch.dict(os.environ, {
            "FLASK_ENV": "production",
            "DB_SSL_CA": "mysql-ca.pem",
            "DB_SSL_VERIFY_CERT": "true",
            "DB_SSL_VERIFY_IDENTITY": "true",
        }):
            validate_production_mysql_tls()


if __name__ == "__main__":
    unittest.main()
