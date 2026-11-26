import contextlib
import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import has_app_context

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from app import create_app  # noqa: E402
from werkzeug.security import check_password_hash  # noqa: E402


class BootstrapScriptTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "bootstrap-tests-only-secret-key-123456789",
            "DB_CONFIG": {},
        })

    def test_create_admin_runs_database_access_in_factory_app_context(self):
        module = importlib.import_module("scripts.create_admin")

        class ExistingAdminCursor:
            def execute(self, *_args):
                self.executed = True

            def fetchone(self):
                return (1,)

            def close(self):
                pass

        class ExistingAdminConnection:
            def cursor(self):
                self.cursor_instance = ExistingAdminCursor()
                return self.cursor_instance

        @contextlib.contextmanager
        def transaction():
            self.assertTrue(has_app_context())
            yield ExistingAdminConnection()

        with patch.object(module.Config, "validate"), patch("app.database.transaction", transaction):
            self.assertEqual(module.main(), 0)

    def test_demo_accounts_hash_passwords_and_create_linked_profiles(self):
        module = importlib.import_module("scripts.create_demo_accounts")

        class DemoCursor:
            lastrowid = 0

            def __init__(self):
                self.executed = []

            def execute(self, query, params=()):
                self.executed.append((query, params))
                if query.lstrip().startswith("INSERT INTO users"):
                    self.lastrowid += 1

            def fetchall(self):
                return []

            def fetchone(self):
                return None

            def close(self):
                pass

        class DemoConnection:
            def __init__(self):
                self.cursor_instance = DemoCursor()

            def cursor(self):
                return self.cursor_instance

        connection = DemoConnection()

        @contextlib.contextmanager
        def transaction():
            self.assertTrue(has_app_context())
            yield connection

        with self.app.app_context(), patch.object(module, "transaction", transaction):
            created, existing = module.create_demo_accounts()

        self.assertEqual(len(created), 5)
        self.assertEqual(existing, [])
        users = [
            params
            for query, params in connection.cursor_instance.executed
            if query.lstrip().startswith("INSERT INTO users")
        ]
        self.assertEqual(len(users), 5)
        for user, account in zip(users, created):
            self.assertEqual(user[3], account[0])
            self.assertTrue(check_password_hash(user[2], account[2]))
        queries = [query for query, _params in connection.cursor_instance.executed]
        self.assertTrue(any("INSERT INTO farmers" in query for query in queries))
        self.assertTrue(any("INSERT INTO trainers" in query for query in queries))

    def test_demo_accounts_skip_existing_role_without_password_reset(self):
        module = importlib.import_module("scripts.create_demo_accounts")

        class ExistingRolesCursor:
            def execute(self, query, params=()):
                self.result = None
                if query.startswith("SELECT id, username, role"):
                    username, email = params
                    for index, (role, full_name, demo_username, demo_email) in enumerate(module.DEMO_ACCOUNTS, 1):
                        if username == demo_username and email == demo_email:
                            self.result = (index, demo_username, role, full_name, "1234567890", demo_email)
                            break
                elif query.startswith("SELECT id FROM farmers") or query.startswith("SELECT id FROM trainers"):
                    self.result = (1,)

            def fetchone(self):
                return self.result

            def close(self):
                pass

        class ExistingRolesConnection:
            def cursor(self):
                return ExistingRolesCursor()

        @contextlib.contextmanager
        def transaction():
            self.assertTrue(has_app_context())
            yield ExistingRolesConnection()

        with self.app.app_context(), patch.object(module, "transaction", transaction):
            created, existing = module.create_demo_accounts()

        self.assertEqual(created, [])
        self.assertEqual(len(existing), 5)


if __name__ == "__main__":
    unittest.main()
