import secrets
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
from app.database import transaction  # noqa: E402

DEMO_ACCOUNTS = (
    ("admin", "Demo Administrator", "demo.admin", "demo.admin@example.com"),
    ("coordinator", "Demo Training Coordinator", "demo.coordinator", "demo.coordinator@example.com"),
    ("trainer", "Demo Agricultural Trainer", "demo.trainer", "demo.trainer@example.com"),
    ("management", "Demo Management User", "demo.management", "demo.management@example.com"),
    ("farmer", "Demo Farmer", "demo.farmer", "demo.farmer@example.com"),
)


def create_demo_accounts():
    created = []
    existing = []
    with transaction() as conn:
        cursor = conn.cursor()
        for role, full_name, username, email in DEMO_ACCOUNTS:
            cursor.execute(
                "SELECT id, username, role, full_name, phone, email FROM users WHERE username=%s OR email=%s",
                (username, email),
            )
            account = cursor.fetchone()
            if account:
                user_id, existing_username, existing_role, existing_name, existing_phone, existing_email = account
                if existing_username != username or existing_role != role or existing_email != email:
                    raise ValueError(
                        f"The reserved demo username or email for {role} is already assigned to a different account; "
                        "no account was changed."
                    )
                existing.append((role, username))
                if role == "farmer":
                    cursor.execute("SELECT id FROM farmers WHERE user_id=%s", (user_id,))
                    if not cursor.fetchone():
                        if not existing_phone:
                            raise ValueError("The existing demo farmer account needs a phone number before its profile can be linked.")
                        cursor.execute(
                            """INSERT INTO farmers
                               (farmer_id, user_id, full_name, village, phone, email)
                               VALUES (%s, %s, %s, 'Demonstration Village', %s, %s)""",
                            (f"DEMO-FARMER-{secrets.token_hex(4).upper()}", user_id, existing_name, existing_phone, email),
                        )
                elif role == "trainer":
                    cursor.execute("SELECT id FROM trainers WHERE user_id=%s", (user_id,))
                    if not cursor.fetchone():
                        if not existing_phone:
                            raise ValueError("The existing demo trainer account needs a phone number before its profile can be linked.")
                        cursor.execute(
                            """INSERT INTO trainers
                               (trainer_id, user_id, full_name, specialization, phone, email)
                               VALUES (%s, %s, %s, 'Demonstration Training', %s, %s)""",
                            (f"DEMO-TRAINER-{secrets.token_hex(4).upper()}", user_id, existing_name, existing_phone, email),
                        )
                continue

            password = secrets.token_urlsafe(24)
            phone = "0000000000"
            cursor.execute(
                """INSERT INTO users
                   (full_name, username, password_hash, role, email, phone, account_status)
                   VALUES (%s, %s, %s, %s, %s, %s, 'active')""",
                (full_name, username, generate_password_hash(password), role, email, phone),
            )
            user_id = cursor.lastrowid

            if role == "farmer":
                cursor.execute(
                    """INSERT INTO farmers
                       (farmer_id, user_id, full_name, village, phone, email)
                       VALUES (%s, %s, %s, 'Demonstration Village', %s, %s)""",
                    (f"DEMO-FARMER-{secrets.token_hex(4).upper()}", user_id, full_name, phone, email),
                )
            elif role == "trainer":
                cursor.execute(
                    """INSERT INTO trainers
                       (trainer_id, user_id, full_name, specialization, phone, email)
                       VALUES (%s, %s, %s, 'Demonstration Training', %s, %s)""",
                    (f"DEMO-TRAINER-{secrets.token_hex(4).upper()}", user_id, full_name, phone, email),
                )
            created.append((role, username, password))

        cursor.close()
    return created, existing


def verify_demo_login(app, role, username, password):
    dashboard = {
        "admin": "/api/dashboard/admin",
        "coordinator": "/api/dashboard/coordinator",
        "trainer": "/api/dashboard/trainer",
        "management": "/api/dashboard/management",
        "farmer": "/api/dashboard/farmer",
    }[role]
    client = app.test_client()
    csrf_response = client.get("/api/auth/csrf")
    if csrf_response.status_code != 200:
        return False
    csrf = csrf_response.get_json()["data"]["csrf_token"]
    login_response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    if login_response.status_code != 200:
        return False
    user = login_response.get_json()["data"]["user"]
    if user["role"] != role:
        return False
    return client.get(dashboard).status_code == 200


def main():
    try:
        Config.validate()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1

    app = create_app()
    try:
        with app.app_context():
            created, existing = create_demo_accounts()
            verification = [
                (role, username, verify_demo_login(app, role, username, password))
                for role, username, password in created
            ]
    except (MySQLError, ValueError) as error:
        message = error.msg if isinstance(error, MySQLError) else str(error)
        print(f"Demonstration account setup failed: {message}", file=sys.stderr)
        return 1

    for role, username in existing:
        print(f"Existing {role} account {username!r} left unchanged.")
    if created:
        print("New demonstration credentials (shown once; save them securely):")
        for role, username, password in created:
            print(f"{role}: username={username} password={password}")
    else:
        print("No demonstration accounts were created.")
    failed = [role for role, _username, passed in verification if not passed]
    for role, _username, passed in verification:
        print(f"{role} login and dashboard: {'PASS' if passed else 'FAIL'}")
    if existing:
        print("Existing account passwords are unknown; their logins were not tested.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
