"""Explicit versioned migrations, separate from health-only initialization."""
from contextlib import closing
from pathlib import Path
from campus_repair.db import open_connection


def migrate(config):
    with closing(open_connection(config)) as db:
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version < 1:
            sql = (Path(__file__).parent / 'migrations/001_workflow.sql').read_text()
            try:
                db.executescript(sql)
            except Exception:
                db.rollback()
                raise
