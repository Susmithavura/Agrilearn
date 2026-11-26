from pathlib import Path


def _migration_was_applied(cursor, version):
    if version == "001_progress_percent":
        cursor.execute(
            """SELECT COUNT(*) FROM information_schema.columns
                 WHERE table_schema=DATABASE()
                   AND table_name='training_progress'
                   AND column_name='progress_percent'"""
        )
        return cursor.fetchone()[0] > 0
    return False


def apply_migrations(cursor, migrations_dir):
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version VARCHAR(100) NOT NULL PRIMARY KEY,
               applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
           ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
    )

    applied = []
    for migration_path in sorted(Path(migrations_dir).glob("*.sql")):
        version = migration_path.stem
        cursor.execute(
            "SELECT version FROM schema_migrations WHERE version=%s",
            (version,),
        )
        if cursor.fetchone():
            continue

        if not _migration_was_applied(cursor, version):
            statements = [
                statement.strip()
                for statement in migration_path.read_text(encoding="utf-8").split(";")
                if statement.strip()
            ]
            for statement in statements:
                cursor.execute(statement)

        cursor.execute(
            "INSERT INTO schema_migrations (version) VALUES (%s)",
            (version,),
        )
        applied.append(version)
    return applied
