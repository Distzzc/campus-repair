"""Application factory. Importing this module does not read configuration."""
from flask import Flask
from campus_repair.config import ConfigurationError, load_config
from campus_repair.db import DatabaseStartupError, close_db, verify_database
from campus_repair.errors import register_errors
from campus_repair.logging_config import configure_requests, emit
from campus_repair.routes.health import blueprint


def validated_config(overrides=None):
    try:
        return load_config(overrides)
    except ConfigurationError as error:
        emit("startup_failed", "ERROR", error_code=error.code, field=error.field, rule=error.rule)
        raise SystemExit(1) from None


def create_app(config=None):
    settings = validated_config(config)
    try:
        verify_database(settings)
    except DatabaseStartupError:
        emit("startup_failed", "ERROR", error_code="DATABASE_INIT_FAILED")
        raise SystemExit(1) from None
    app = Flask(__name__, static_folder=None)
    app.config.update(settings)
    app.config.update(DEBUG=False, TESTING=False)
    configure_requests(app)
    register_errors(app)
    app.teardown_appcontext(close_db)
    app.register_blueprint(blueprint)
    emit("startup_completed", minimum_level=settings["LOG_LEVEL"])
    return app
