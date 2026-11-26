import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from scripts import prepare_environment  # noqa: E402
from dotenv import dotenv_values  # noqa: E402


class EnvironmentSetupTests(unittest.TestCase):
    def test_creates_secret_without_changing_database_password(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env_path = root / ".env"
            example_path = root / ".env.example"
            example_path.write_text(
                "SECRET_KEY=replace-with-a-random-secret-at-least-32-characters\n"
                "DB_PASSWORD=existing-db-password-value\n",
                encoding="utf-8",
            )
            with patch.object(prepare_environment, "ENV_PATH", env_path), patch.object(
                prepare_environment, "EXAMPLE_PATH", example_path
            ):
                prepare_environment.ensure_environment()
            values = dotenv_values(env_path)
            self.assertGreaterEqual(len(values["SECRET_KEY"]), 32)
            self.assertNotEqual(values["SECRET_KEY"], "replace-with-a-random-secret-at-least-32-characters")
            self.assertEqual(values["DB_PASSWORD"], "existing-db-password-value")

    def test_preserves_existing_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env_path = root / ".env"
            example_path = root / ".env.example"
            secret = "existing-random-secret-value-that-is-long-enough"
            env_path.write_text(f"SECRET_KEY={secret}\nDB_PASSWORD=do-not-change\n", encoding="utf-8")
            with patch.object(prepare_environment, "ENV_PATH", env_path), patch.object(
                prepare_environment, "EXAMPLE_PATH", example_path
            ):
                prepare_environment.ensure_environment()
            values = dotenv_values(env_path)
            self.assertEqual(values["SECRET_KEY"], secret)
            self.assertEqual(values["DB_PASSWORD"], "do-not-change")


if __name__ == "__main__":
    unittest.main()
