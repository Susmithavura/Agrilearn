from datetime import timedelta
import secrets

from flask import Flask, jsonify, request, session
from flask_cors import CORS
from mysql.connector import Error as MySQLError, IntegrityError, errorcode
from werkzeug.exceptions import HTTPException

from .config import Config
from .database import ping_database


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    app.permanent_session_lifetime = timedelta(
        minutes=app.config["SESSION_LIFETIME_MINUTES"]
    )

    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}},
        supports_credentials=True,
        allow_headers=["Content-Type", "X-CSRF-Token"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        max_age=600,
    )

    from .routes import api

    app.register_blueprint(api, url_prefix="/api")

    @app.before_request
    def protect_state_changes():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        if request.path in {"/api/auth/login", "/api/auth/csrf"}:
            return None
        expected = session.get("csrf_token")
        supplied = request.headers.get("X-CSRF-Token")
        if not expected or not supplied or not secrets.compare_digest(expected, supplied):
            return jsonify(error={"code": "csrf_failed", "message": "Reload the page and try again."}), 403
        return None

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return jsonify(error={"code": error.name.lower().replace(" ", "_"), "message": error.description}), error.code

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(error):
        if error.errno == errorcode.ER_DUP_ENTRY:
            return jsonify(error={"code": "duplicate_record", "message": "A record with one of these unique values already exists."}), 409
        if error.errno == errorcode.ER_ROW_IS_REFERENCED_2:
            return jsonify(error={"code": "record_in_use", "message": "This record has related training history. Archive or deactivate it instead."}), 409
        app.logger.warning("Database integrity constraint rejected a request (errno=%s)", error.errno)
        return jsonify(error={"code": "integrity_error", "message": "The request conflicts with related records."}), 409

    @app.errorhandler(MySQLError)
    def handle_database_error(error):
        app.logger.error("Database service is unavailable (errno=%s)", getattr(error, "errno", "unknown"))
        return jsonify(error={"code": "database_unavailable", "message": "The database is temporarily unavailable."}), 503

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled request failure")
        return jsonify(error={"code": "internal_error", "message": "The request could not be completed."}), 500

    return app


__all__ = ["create_app", "ping_database"]
