import re
import secrets

from flask import g, jsonify, request, session
from werkzeug.security import check_password_hash

from ..database import fetch_one, transaction
from ..routes import api
from ..security import csrf_token, login_required, api_error, get_json, required_text


@api.get("/health")
def health():
    return jsonify(data={"status": "ok"})


@api.get("/health/database")
def database_health():
    from ..database import ping_database

    if not ping_database():
        return api_error("The database is unavailable or not initialized.", 503, "database_unavailable")
    return jsonify(data={"status": "ok", "database": "connected"})


@api.get("/auth/csrf")
def get_csrf():
    session.permanent = True
    return jsonify(data={"csrf_token": csrf_token()})


@api.post("/auth/login")
def login():
    try:
        expected = session.get("csrf_token")
        supplied = request.headers.get("X-CSRF-Token")
        if not expected or not supplied or not secrets.compare_digest(expected, supplied):
            return api_error("Reload the page and try again.", 403, "csrf_failed")
        body = get_json()
        username = required_text(body, "username", "Username", 80)
        password = body.get("password")
        if not isinstance(password, str) or not password or len(password) > 1024:
            return api_error("Username or password is incorrect.", 401, "invalid_credentials")
        user = fetch_one(
            """SELECT id, full_name, username, password_hash, role, email, phone,
                      account_status, language_preference
                 FROM users WHERE username = %s""",
            (username,),
        )
    except ValueError as error:
        return api_error(str(error), 400)
    if not user or user["account_status"] != "active" or not check_password_hash(user["password_hash"], password):
        return api_error("Username or password is incorrect.", 401, "invalid_credentials")

    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    token = csrf_token()
    return jsonify(data={
        "user": _public_user(user),
        "csrf_token": token,
    })


@api.post("/auth/logout")
@login_required
def logout():
    session.clear()
    return jsonify(data={"logged_out": True})


@api.get("/auth/me")
@login_required
def me():
    return jsonify(data={
        "user": _public_user(g.user),
        "csrf_token": csrf_token(),
    })


@api.patch("/auth/profile")
@login_required
def update_profile():
    try:
        body = get_json()
        allowed = {"full_name", "email", "phone", "language_preference"}
        if set(body) - allowed:
            return api_error("Only name, contact details and language preference may be changed here.", 400)
        values = {}
        if "full_name" in body:
            values["full_name"] = required_text(body, "full_name", "Full name", 160)
        if "email" in body:
            values["email"] = _email(body.get("email"), required=False)
        if "phone" in body:
            values["phone"] = _phone(body.get("phone"), required=False)
        if "language_preference" in body:
            language = body.get("language_preference")
            if language not in {"en", "te", "hi"}:
                return api_error("Language preference must be en, te or hi.", 400)
            values["language_preference"] = language
        if not values:
            return api_error("At least one profile field is required.", 400)
        setters = ", ".join(f"{key} = %s" for key in values)
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE users SET {setters} WHERE id = %s", (*values.values(), g.user["id"]))
            cursor.close()
        updated = fetch_one(
            """SELECT id, full_name, username, role, email, phone, account_status,
                      language_preference FROM users WHERE id = %s""",
            (g.user["id"],),
        )
        return jsonify(data={"user": _public_user(updated), "csrf_token": csrf_token()})
    except ValueError as error:
        return api_error(str(error), 400)


@api.post("/auth/change-password")
@login_required
def change_password():
    try:
        body = get_json()
        current_password = body.get("current_password")
        new_password = body.get("new_password")
        if not isinstance(current_password, str) or not isinstance(new_password, str):
            return api_error("Current and new passwords are required.", 400)
        if len(new_password) < 12 or len(new_password) > 1024:
            return api_error("New password must contain at least 12 characters.", 400)
        row = fetch_one("SELECT password_hash FROM users WHERE id = %s", (g.user["id"],))
        if not row or not check_password_hash(row["password_hash"], current_password):
            return api_error("Current password is incorrect.", 400, "current_password_incorrect")
        from werkzeug.security import generate_password_hash

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (generate_password_hash(new_password), g.user["id"]))
            cursor.close()
        session.clear()
        return jsonify(data={"password_changed": True, "logged_out": True})
    except ValueError as error:
        return api_error(str(error), 400)


def _public_user(user):
    return {
        "id": str(user["id"]),
        "full_name": user["full_name"],
        "name": user["full_name"],
        "username": user["username"],
        "role": user["role"],
        "email": user.get("email"),
        "phone": user.get("phone"),
        "account_status": user["account_status"],
        "status": "Active" if user["account_status"] == "active" else "Inactive",
        "language_preference": user.get("language_preference", "en"),
    }


def _email(value, required=False):
    if value is None or value == "":
        if required:
            raise ValueError("Email address is required.")
        return None
    if not isinstance(value, str):
        raise ValueError("Email address must be text.")
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise ValueError("Enter a valid email address.")
    return value


def _phone(value, required=False):
    if value is None or value == "":
        if required:
            raise ValueError("Phone number is required.")
        return None
    if not isinstance(value, str):
        raise ValueError("Phone number must be text.")
    value = value.strip()
    if not re.fullmatch(r"[0-9+() .-]{7,32}", value):
        raise ValueError("Enter a valid phone number.")
    return value
