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
    app = Flask(__name__)
    app.config.update(settings)
    app.config.update(DEBUG=False, TESTING=False)
    configure_requests(app)
    register_errors(app)
    app.teardown_appcontext(close_db)
    app.register_blueprint(blueprint)
    from campus_repair.routes.portal import blueprint as portal_blueprint
    from campus_repair.services.accounts import BusinessError
    app.register_blueprint(portal_blueprint)
    app.config['MAX_CONTENT_LENGTH'] = 6 * 1024 * 1024

    @app.errorhandler(BusinessError)
    def business_error(error):
        from flask import g, jsonify
        g.error_code = error.code
        return jsonify(error={'code': error.code, 'message': error.message, 'details': {}}, request_id=g.request_id), error.status

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' blob: data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if response.mimetype == 'text/html':
            response.headers['Cache-Control'] = 'no-store'
        return response

    emit("startup_completed", minimum_level=settings["LOG_LEVEL"])
    return app
