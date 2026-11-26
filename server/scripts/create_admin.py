import getpass
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from mysql.connector import Error as MySQLError
from werkzeug.security import generate_password_hash

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))
from scripts.prepare_environment import ensure_environment  # noqa: E402

ensure_environment()
load_dotenv(SERVER_ROOT / ".env")

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402


def main():
    try:
        Config.validate()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1

    app = create_app()
    with app.app_context():
        return create_admin()


def create_admin():
    from app.database import transaction

    try:
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
            admin_exists = cursor.fetchone()[0] > 0
            cursor.close()
        if admin_exists:
            print("An administrator already exists. No account was changed.")
            return 0
    except MySQLError as error:
        print(f"Could not check for an existing administrator (MySQL {error.errno}): {error.msg}", file=sys.stderr)
        return 1

    full_name = input("Administrator full name: ").strip()
    username = input("Administrator username: ").strip()
    if not full_name or len(full_name) > 160:
        print("Name must contain 1–160 characters.", file=sys.stderr)
        return 1
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,80}", username):
        print("Username must be 3–80 characters using letters, numbers, dot, underscore or hyphen.", file=sys.stderr)
        return 1
    password = getpass.getpass("Administrator password (min. 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if len(password) < 12:
        print("Use a password of at least 12 characters.", file=sys.stderr)
        return 1
    if password != confirmation:
        print("Passwords did not match.", file=sys.stderr)
        return 1
    try:
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT GET_LOCK(%s, 5)", ("agrilearn_bootstrap_admin",))
            if cursor.fetchone()[0] != 1:
                print("Another administrator setup is in progress. Try again shortly.", file=sys.stderr)
                return 1
            cursor.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
            admin_count = cursor.fetchone()[0]
            if admin_count:
                print("An administrator already exists. Use the authenticated administrator user-management API to add another.", file=sys.stderr)
                return 1
            cursor.execute(
                """INSERT INTO users (full_name,username,password_hash,role,account_status)
                   VALUES (%s,%s,%s,'admin','active')""",
                (full_name, username, generate_password_hash(password)),
            )
            user_id = cursor.lastrowid
            cursor.execute("INSERT INTO audit_log (user_id,action,entity_type,entity_id) VALUES (%s,'bootstrap','user',%s)", (user_id,user_id))
            cursor.close()
        print(f"Administrator account {username!r} created.")
        return 0
    except MySQLError as error:
        print(f"Administrator account creation failed (MySQL {error.errno}): {error.msg}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
