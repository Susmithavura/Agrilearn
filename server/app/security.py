from functools import wraps
import secrets

from flask import g, jsonify, session


ROLES = {"admin", "coordinator", "trainer", "farmer", "management"}


def api_error(message, status, code="invalid_request"):
    return jsonify(error={"code": code, "message": message}), status


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return api_error("Authentication is required.", 401, "authentication_required")
        from .database import fetch_one

        user = fetch_one(
            """SELECT id, full_name, username, role, email, phone, account_status,
                      language_preference
                 FROM users WHERE id = %s""",
            (user_id,),
        )
        if not user or user["account_status"] != "active":
            session.clear()
            return api_error("Authentication is required.", 401, "authentication_required")
        g.user = user
        return view(*args, **kwargs)

    return wrapped


def roles_required(*roles):
    invalid = set(roles) - ROLES
    if invalid:
        raise ValueError(f"Unknown roles: {', '.join(sorted(invalid))}")

    def decorate(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            from flask import g

            if g.user["role"] not in roles:
                return api_error("You do not have permission to perform this action.", 403, "permission_denied")
            return view(*args, **kwargs)

        return wrapped

    return decorate


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def get_json():
    from flask import request

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("A JSON object is required.")
    return data


def required_text(data, key, label=None, maximum=255):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label or key.replace('_', ' ').capitalize()} is required.")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{label or key.replace('_', ' ').capitalize()} must be {maximum} characters or fewer.")
    return value


def optional_text(data, key, maximum=255):
    value = data.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key.replace('_', ' ').capitalize()} must be text.")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{key.replace('_', ' ').capitalize()} must be {maximum} characters or fewer.")
    return value or None


def enum_value(data, key, options, label=None, default=None):
    value = data.get(key, default)
    if value not in options:
        raise ValueError(f"{label or key.replace('_', ' ').capitalize()} must be one of: {', '.join(options)}.")
    return value


def positive_id(value, label="id"):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label.capitalize()} must be a positive integer.") from None
    if parsed < 1:
        raise ValueError(f"{label.capitalize()} must be a positive integer.")
    return parsed


def parse_data(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            from flask import request

            if request.method in {"POST", "PUT", "PATCH"}:
                request.validated_json = get_json()
            return view(*args, **kwargs)
        except ValueError as error:
            return api_error(str(error), 400)

    return wrapped
