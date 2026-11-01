"""SQLite infrastructure. No imports from routes or business services."""
import os
from pathlib import Path
import sqlite3
from contextlib import closing

from flask import current_app, g


class DatabaseStartupError(Exception):
    """Safe signal; underlying database errors must not be rendered."""


def open_connection(config, *, initialize=False):
    path = Path(config["DATABASE_PATH"])
    if path.exists() and (not os.access(path, os.R_OK | os.W_OK)
                          or not path.stat().st_mode & 0o444
                          or not path.stat().st_mode & 0o222):
        raise sqlite3.OperationalError("Database unavailable")
    mode = "rwc" if initialize else "rw"
    connection = sqlite3.connect(f"{path.as_uri()}?mode={mode}", uri=True,
                                 timeout=config["DB_TIMEOUT_SECONDS"])
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {config['DB_TIMEOUT_SECONDS'] * 1000}")
    except Exception:
        connection.close()
        raise
    return connection


def probe(connection):
    # Read actual database metadata as well as executing the documented query.
    # This rejects corrupt files that a constant-only SELECT could overlook.
    connection.execute("PRAGMA schema_version").fetchone()
    if connection.execute("SELECT 1").fetchone() != (1,):
        raise sqlite3.DatabaseError("Database unavailable")


def initialize_database(config):
    try:
        with closing(open_connection(config, initialize=True)) as connection:
            probe(connection)
    except (sqlite3.Error, OSError):
        raise DatabaseStartupError() from None


def verify_database(config):
    try:
        with closing(open_connection(config)) as connection:
            probe(connection)
    except (sqlite3.Error, OSError):
        raise DatabaseStartupError() from None


def get_db():
    if "database" not in g:
        g.database = open_connection(current_app.config)
    return g.database


def close_db(_error=None):
    connection = g.pop("database", None)
    if connection is not None:
        connection.close()
