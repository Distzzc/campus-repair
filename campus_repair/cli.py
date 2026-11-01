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

    return app
