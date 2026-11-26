import sys
import tempfile
import unittest
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from scripts.migrations import apply_migrations  # noqa: E402


class MigrationCursor:
    def __init__(self, progress_column_exists=False):
        self.progress_column_exists = progress_column_exists
        self.applied = set()
        self.statements = []
        self.result = None

    def execute(self, statement, params=()):
        self.statements.append(statement)
        if statement.startswith("SELECT version FROM schema_migrations"):
            self.result = (params[0],) if params[0] in self.applied else None
        elif "information_schema.columns" in statement:
            self.result = (int(self.progress_column_exists),)
        elif statement.startswith("ALTER TABLE training_progress"):
            self.progress_column_exists = True
        elif statement.startswith("INSERT INTO schema_migrations"):
            self.applied.add(params[0])

    def fetchone(self):
        return self.result


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.migrations_dir = Path(self.directory.name)
        (self.migrations_dir / "001_progress_percent.sql").write_text(
            "ALTER TABLE training_progress ADD COLUMN progress_percent TINYINT UNSIGNED NOT NULL DEFAULT 0;\n"
            "UPDATE training_progress SET progress_percent=0;",
            encoding="utf-8",
        )

    def tearDown(self):
        self.directory.cleanup()

    def test_applies_migration_once_and_records_version(self):
        cursor = MigrationCursor()
        applied = apply_migrations(cursor, self.migrations_dir)
        self.assertEqual(applied, ["001_progress_percent"])
        self.assertIn("001_progress_percent", cursor.applied)
        self.assertEqual(apply_migrations(cursor, self.migrations_dir), [])
        self.assertEqual(
            sum(statement.startswith("ALTER TABLE training_progress") for statement in cursor.statements),
            1,
        )

    def test_existing_untracked_schema_is_baselined_without_reapplying_ddl(self):
        cursor = MigrationCursor(progress_column_exists=True)
        applied = apply_migrations(cursor, self.migrations_dir)
        self.assertEqual(applied, ["001_progress_percent"])
        self.assertNotIn(
            "ALTER TABLE training_progress ADD COLUMN progress_percent TINYINT UNSIGNED NOT NULL DEFAULT 0",
            cursor.statements,
        )
        self.assertIn("001_progress_percent", cursor.applied)


if __name__ == "__main__":
    unittest.main()
