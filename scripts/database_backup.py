"""Consistent SQLite backup/restore to a new destination, never overwrite data."""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3

from campus_repair.logging_config import emit


def copy_database(source, destination):
    source, destination = Path(source).absolute(), Path(destination).absolute()
    # Exclusive creation prevents accidentally replacing any existing file.
    created = False
    try:
        with closing(sqlite3.connect(f'{source.as_uri()}?mode=ro', uri=True)) as reader:
            with destination.open('xb'):
                created = True
            with closing(sqlite3.connect(destination)) as writer:
                reader.backup(writer)
                if writer.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                    raise sqlite3.DatabaseError('Integrity check failed')
    except (OSError, sqlite3.Error):
        if created:
            destination.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description='Consistent backup/restore without overwriting destinations')
    parser.add_argument('action', choices=['backup', 'restore'])
    parser.add_argument('source')
    parser.add_argument('destination')
    args = parser.parse_args()
    try:
        copy_database(args.source, args.destination)
    except (OSError, sqlite3.Error):
        emit('backup_failed', 'ERROR', error_code='BACKUP_FAILED')
        return 1
    emit('backup_completed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
