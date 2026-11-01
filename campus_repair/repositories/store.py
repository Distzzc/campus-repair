"""Parameterized SQLite access and transaction boundary primitives."""
from contextlib import contextmanager
import sqlite3
from campus_repair.db import get_db


def connection():
    db = get_db()
    db.row_factory = sqlite3.Row
    return db


def one(sql, parameters=()):
    row = connection().execute(sql, parameters).fetchone()
    return dict(row) if row else None


def many(sql, parameters=()):
    return [dict(row) for row in connection().execute(sql, parameters).fetchall()]


def execute(sql, parameters=()):
    return connection().execute(sql, parameters)


@contextmanager
def transaction():
    db = connection()
    db.execute('BEGIN IMMEDIATE')
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise
