import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def mysql_tls_options():
    options = {
        "ssl_verify_cert": env_bool("DB_SSL_VERIFY_CERT", False),
        "ssl_verify_identity": env_bool("DB_SSL_VERIFY_IDENTITY", False),
    }
    ca_file = os.getenv("DB_SSL_CA", "").strip()
    if ca_file:
        options["ssl_ca"] = ca_file
    return options


def validate_production_mysql_tls(environment=None, options=None):
    environment = environment or os.getenv("FLASK_ENV", "development").strip().lower()
    options = options or mysql_tls_options()
    if environment != "production":
        return
    if not options.get("ssl_ca") or not options["ssl_verify_cert"] or not options["ssl_verify_identity"]:
        raise RuntimeError(
            "Production MySQL requires DB_SSL_CA, DB_SSL_VERIFY_CERT=true and DB_SSL_VERIFY_IDENTITY=true."
        )


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "")
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:8000").rstrip("/")
    FLASK_ENV = os.getenv("FLASK_ENV", "development").strip().lower()
    FLASK_DEBUG = env_bool("FLASK_DEBUG", False)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax").strip().capitalize()
    SESSION_REFRESH_EACH_REQUEST = True
    SESSION_LIFETIME_MINUTES = int(os.getenv("SESSION_LIFETIME_MINUTES", "60"))
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=SESSION_LIFETIME_MINUTES)
    DB_APP_ALLOWED_HOST = os.getenv("DB_APP_ALLOWED_HOST", "localhost").strip()
    DB_CONFIG = {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "database": os.getenv("DB_NAME", "agrilearn_db"),
        "user": os.getenv("DB_USER", "agrilearn_app"),
        "password": os.getenv("DB_PASSWORD", ""),
        "charset": "utf8mb4",
        "autocommit": False,
        "connection_timeout": 5,
        **mysql_tls_options(),
    }

    @staticmethod
    def validate():
        if len(Config.SECRET_KEY) < 32 or Config.SECRET_KEY == "replace-with-a-random-secret-at-least-32-characters":
            raise RuntimeError("Set SECRET_KEY to a random secret of at least 32 characters in server/.env.")
        if not Config.DB_CONFIG["password"]:
            raise RuntimeError("Set DB_PASSWORD for the least-privilege MySQL application account in server/.env.")
        if Config.SESSION_LIFETIME_MINUTES < 5:
            raise RuntimeError("SESSION_LIFETIME_MINUTES must be at least 5.")
        if Config.SESSION_COOKIE_SAMESITE not in {"Lax", "Strict", "None"}:
            raise RuntimeError("SESSION_COOKIE_SAMESITE must be Lax, Strict or None.")
        if Config.SESSION_COOKIE_SAMESITE == "None" and not Config.SESSION_COOKIE_SECURE:
            raise RuntimeError("SESSION_COOKIE_SECURE=true is required when SESSION_COOKIE_SAMESITE=None.")
        if not Config.DB_APP_ALLOWED_HOST or any(char in Config.DB_APP_ALLOWED_HOST for char in "%_"):
            raise RuntimeError("Set DB_APP_ALLOWED_HOST to the exact application client hostname or IP (wildcards are not allowed).")

        try:
            frontend = urlsplit(Config.FRONTEND_ORIGIN)
            frontend.port
        except ValueError as error:
            raise RuntimeError("FRONTEND_ORIGIN must be one exact HTTP(S) origin with a valid port.") from error
        if (
            frontend.scheme not in {"http", "https"}
            or not frontend.netloc
            or frontend.username is not None
            or frontend.password is not None
            or frontend.path
            or frontend.query
            or frontend.fragment
            or "," in Config.FRONTEND_ORIGIN
        ):
            raise RuntimeError("FRONTEND_ORIGIN must be one exact HTTP(S) origin with no path.")

        if Config.FLASK_ENV == "production":
            allowed_host = os.getenv("DB_APP_ALLOWED_HOST", "").strip()
            if not allowed_host or any(char in allowed_host for char in "%_"):
                raise RuntimeError("Set DB_APP_ALLOWED_HOST to the exact production application client hostname or IP (wildcards are not allowed).")
            if not Config.SESSION_COOKIE_SECURE:
                raise RuntimeError("Set SESSION_COOKIE_SECURE=true in production.")
            if Config.FLASK_DEBUG:
                raise RuntimeError("Set FLASK_DEBUG=0 in production.")
            if frontend.scheme != "https":
                raise RuntimeError("FRONTEND_ORIGIN must use HTTPS in production.")
            validate_production_mysql_tls(Config.FLASK_ENV, Config.DB_CONFIG)
