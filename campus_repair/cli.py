"""Initialization-only factory: never serves health or bypasses normal startup."""
import click
from flask import Flask
from campus_repair import validated_config
from campus_repair.db import DatabaseStartupError, initialize_database
from campus_repair.logging_config import emit


def create_cli_app():
    app = Flask(__name__, static_folder=None)
    app.config.update(validated_config())

    @app.cli.command("init-db")
    def init_db():
        try:
            initialize_database(app.config)
        except DatabaseStartupError:
            emit("startup_failed", "ERROR", error_code="DATABASE_INIT_FAILED")
            raise click.exceptions.Exit(1) from None
        emit("database_initialized", minimum_level=app.config["LOG_LEVEL"])

    @app.cli.command('migrate-db')
    def migrate_db():
        from campus_repair.migration import migrate
        migrate(app.config)
        emit('database_migrated')

    @app.cli.command('seed-demo')
    @click.option('--reset', is_flag=True)
    @click.option('--yes', is_flag=True)
    def seed_demo(reset, yes):
        from campus_repair.db import close_db
        from campus_repair.services.demo import seed
        if reset and not yes:
            raise click.ClickException('Reset requires --yes')
        app.teardown_appcontext(close_db)
        seed(app.config['DEMO_PASSWORD'], reset=reset)
        emit('demo_seeded')

    return app
