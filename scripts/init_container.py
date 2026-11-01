"""One-shot volume setup. No recursive ownership changes or arbitrary paths."""
import os
from pathlib import Path

from campus_repair.config import ConfigurationError, decimal_integer
from campus_repair.logging_config import emit


def main():
    try:
        decimal_integer(os.environ.get('HOST_PORT', '8000'), 'HOST_PORT', 1024, 65535)
    except ConfigurationError as error:
        emit('startup_failed', 'ERROR', error_code=error.code, field=error.field, rule=error.rule)
        return 1
    # These are fixed container paths; never use a caller-provided path as root.
    directory = Path('/data')
    database = directory / 'campus-repair.sqlite3'
    if directory.is_symlink() or database.is_symlink():
        emit('startup_failed', 'ERROR', error_code='DATABASE_INIT_FAILED')
        return 1
    try:
        directory.mkdir(exist_ok=True)
        os.chown(directory, 10001, 10001)
        if database.exists():
            os.chown(database, 10001, 10001)
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
    except OSError:
        emit('startup_failed', 'ERROR', error_code='DATABASE_INIT_FAILED')
        return 1
    os.environ['FLASK_SKIP_DOTENV'] = '1'
    from campus_repair.cli import create_cli_app
    from campus_repair.db import initialize_database, close_db
    from campus_repair.migration import migrate
    from campus_repair.services.demo import seed
    app = create_cli_app()
    initialize_database(app.config)
    migrate(app.config)
    app.teardown_appcontext(close_db)
    with app.app_context():
        if app.config['DEMO_MODE']:
            seed(app.config['DEMO_PASSWORD'])
    emit('database_ready')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
