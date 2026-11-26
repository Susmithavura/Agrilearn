from app import create_app
from app.config import Config


Config.validate()
app = create_app()
