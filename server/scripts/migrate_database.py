import getpass
import os
import re
import sys
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))
from app.config import mysql_tls_options, validate_production_mysql_tls  # noqa: E402
from scripts.migrations import apply_migrations  # noqa: E402

load_dotenv(SERVER_ROOT / ".env")

DB_NAME = os.getenv("DB_NAME", "agrilearn_db")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
ADMIN_HOST = os.getenv("MYSQL_ADMIN_HOST", DB_HOST)
ADMIN_PORT = int(os.getenv("MYSQL_ADMIN_PORT", str(DB_PORT)))


def main():
    try:
        validate_production_mysql_tls()
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", DB_NAME):
        print("DB_NAME must use only letters, numbers and underscores.", file=sys.stderr)
        return 1

    admin_user = os.getenv("MYSQL_ADMIN_USER") or input("MySQL migration administrator username [root]: ").strip() or "root"
    admin_password = os.getenv("MYSQL_ADMIN_PASSWORD") or getpass.getpass("MySQL migration administrator password: ")
    try:
        connection = mysql.connector.connect(
            host=ADMIN_HOST,
            port=ADMIN_PORT,
            user=admin_user,
            password=admin_password,
            database=DB_NAME,
            charset="utf8mb4",
            connection_timeout=8,
            autocommit=True,
            **mysql_tls_options(),
        )
    except mysql.connector.Error as error:
        print(f"Could not connect to the target database: {error.msg}", file=sys.stderr)
        return 1

    try:
        cursor = connection.cursor()
        applied = apply_migrations(cursor, SERVER_ROOT / "sql" / "migrations")
        cursor.close()
        if applied:
            print(f"Applied migrations: {', '.join(applied)}")
        else:
            print("Database schema is already at the latest migration.")
        return 0
    except (OSError, mysql.connector.Error) as error:
        print(f"Database migration failed: {error}", file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
