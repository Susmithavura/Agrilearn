import getpass
import os
import re
import sys
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv, set_key

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))
from app.config import mysql_tls_options, validate_production_mysql_tls  # noqa: E402
from scripts.migrations import apply_migrations  # noqa: E402
from scripts.prepare_environment import ensure_environment  # noqa: E402

ensure_environment()
load_dotenv(SERVER_ROOT / ".env")

DB_NAME = os.getenv("DB_NAME", "agrilearn_db")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
ADMIN_HOST = os.getenv("MYSQL_ADMIN_HOST", os.getenv("DB_HOST", "127.0.0.1"))
ADMIN_PORT = int(os.getenv("MYSQL_ADMIN_PORT", str(DB_PORT)))
APP_USER = os.getenv("DB_USER", "agrilearn_app")
APP_ALLOWED_HOST = os.getenv(
    "DB_APP_ALLOWED_HOST",
    "localhost" if DB_HOST in {"localhost", "127.0.0.1"} else "",
)


def fail(message):
    print(f"Setup failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def quote_literal(connection, value):
    escaped = connection.converter.escape(str(value))
    if not isinstance(escaped, str):
        escaped = escaped.decode("utf-8")
    return "'" + escaped + "'"


def main():
    try:
        validate_production_mysql_tls()
    except RuntimeError as error:
        fail(str(error))
    if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", DB_NAME):
        fail("DB_NAME must use only letters, numbers and underscores.")
    if not re.fullmatch(r"[A-Za-z0-9_]{1,32}", APP_USER):
        fail("DB_USER must use only letters, numbers and underscores.")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,255}", DB_HOST):
        fail("DB_HOST must be a hostname or IP address.")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,255}", APP_ALLOWED_HOST):
        fail("DB_APP_ALLOWED_HOST must be the exact application client hostname or IP (wildcards are not allowed).")

    admin_user = os.getenv("MYSQL_ADMIN_USER") or input("MySQL administrator username [root]: ").strip() or "root"
    admin_password = os.getenv("MYSQL_ADMIN_PASSWORD") or getpass.getpass("MySQL administrator password: ")
    app_password = os.getenv("DB_PASSWORD")
    if not app_password:
        app_password = os.getenv("DB_SETUP_PASSWORD") or getpass.getpass(
            "AgriLearn database account password (existing password, or new password; min. 20 characters): "
        )
        confirm_password = os.getenv("DB_SETUP_PASSWORD") or getpass.getpass("Confirm AgriLearn database password: ")
        if len(app_password) < 20:
            fail("Choose or enter an application account password of at least 20 characters.")
        if app_password != confirm_password:
            fail("The application database passwords did not match.")

    try:
        admin = mysql.connector.connect(
            host=ADMIN_HOST,
            port=ADMIN_PORT,
            user=admin_user,
            password=admin_password,
            charset="utf8mb4",
            connection_timeout=8,
            autocommit=True,
            **mysql_tls_options(),
        )
    except mysql.connector.Error as error:
        fail(f"Could not connect to MySQL at {ADMIN_HOST}:{ADMIN_PORT} as {admin_user}. {error.msg}")

    try:
        cursor = admin.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        cursor.execute(f"USE `{DB_NAME}`")
        schema_path = SERVER_ROOT / "sql" / "schema.sql"
        statements = [statement.strip() for statement in schema_path.read_text(encoding="utf-8").split(";") if statement.strip()]
        for statement in statements:
            cursor.execute(statement)
        apply_migrations(cursor, SERVER_ROOT / "sql" / "migrations")

        account = f"{quote_literal(admin, APP_USER)}@{quote_literal(admin, APP_ALLOWED_HOST)}"
        password_literal = quote_literal(admin, app_password)
        cursor.execute(f"CREATE USER IF NOT EXISTS {account} IDENTIFIED BY {password_literal}")
        cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON `{DB_NAME}`.* TO {account}")
        cursor.execute("FLUSH PRIVILEGES")
        cursor.close()
        admin.close()

        app_connection = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=APP_USER,
            password=app_password,
            database=DB_NAME,
            charset="utf8mb4",
            connection_timeout=8,
            **mysql_tls_options(),
        )
        verify = app_connection.cursor()
        verify.execute("SHOW TABLES")
        tables = [row[0] for row in verify.fetchall()]
        verify.close()
        app_connection.close()
        required = {"users", "farmers", "trainers", "training_programs", "training_sessions", "program_farmers", "attendance", "training_progress"}
        missing = sorted(required - set(tables))
        if missing:
            fail(f"Schema verification failed; missing tables: {', '.join(missing)}.")
        set_key(str(SERVER_ROOT / ".env"), "DB_PASSWORD", app_password, quote_mode="always")
        print(f"Database {DB_NAME!r} created/verified successfully ({len(tables)} tables).")
        print(f"Least-privilege account {APP_USER!r}@{APP_ALLOWED_HOST!r} can read and modify application data.")
        print("The application database password was saved to the ignored server/.env file.")
        print("No user accounts or sample records were created.")
    except mysql.connector.Error as error:
        fail(f"MySQL setup could not complete. {error.msg}")
    finally:
        if admin.is_connected():
            admin.close()


if __name__ == "__main__":
    main()
