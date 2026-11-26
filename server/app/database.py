from contextlib import contextmanager

import mysql.connector
from flask import current_app


@contextmanager
def connection():
    db_config = current_app.config["DB_CONFIG"]
    conn = mysql.connector.connect(**db_config)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction():
    with connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def ping_database():
    try:
        with connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT COUNT(*) FROM information_schema.tables
                     WHERE table_schema = DATABASE()
                       AND table_name IN (
                         'users','farmers','trainers','training_programs',
                         'training_sessions','program_farmers','attendance',
                         'training_progress','audit_log'
                       )"""
            )
            result = cursor.fetchone()
            cursor.close()
            return bool(result and result[0] == 9)
    except mysql.connector.Error:
        return False


def fetch_one(query, params=()):
    with connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params)
        row = cursor.fetchone()
        cursor.close()
        return row


def fetch_all(query, params=()):
    with connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        return rows
