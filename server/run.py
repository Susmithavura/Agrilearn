import os

from scripts.prepare_environment import ensure_environment

ensure_environment()

from app import create_app
from app.config import Config


Config.validate()
app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
