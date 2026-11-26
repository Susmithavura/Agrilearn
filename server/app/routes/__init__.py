from flask import Blueprint

api = Blueprint("api", __name__)

from . import auth, resources, reports, dashboard  # noqa: E402,F401
