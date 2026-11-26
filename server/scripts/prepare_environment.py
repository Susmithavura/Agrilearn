import secrets
import shutil
import sys
from pathlib import Path

from dotenv import dotenv_values, set_key

SERVER_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = SERVER_ROOT / ".env"
EXAMPLE_PATH = SERVER_ROOT / ".env.example"
PLACEHOLDER_SECRET = "replace-with-a-random-secret-at-least-32-characters"


def ensure_environment():
    if not ENV_PATH.exists():
        if not EXAMPLE_PATH.is_file():
            raise FileNotFoundError(f"Environment template was not found: {EXAMPLE_PATH}")
        shutil.copyfile(EXAMPLE_PATH, ENV_PATH)

    values = dotenv_values(ENV_PATH)
    secret = values.get("SECRET_KEY")
    if not secret or secret == PLACEHOLDER_SECRET:
        set_key(str(ENV_PATH), "SECRET_KEY", secrets.token_urlsafe(48), quote_mode="always")
    elif len(secret) < 32:
        raise ValueError("The existing SECRET_KEY in server/.env is too short. Replace it with a random value of at least 32 characters.")
    return ENV_PATH


if __name__ == "__main__":
    try:
        path = ensure_environment()
        print(f"Environment configuration is ready: {path}")
    except (OSError, ValueError) as error:
        print(f"Could not prepare environment configuration: {error}", file=sys.stderr)
        raise SystemExit(1) from error
