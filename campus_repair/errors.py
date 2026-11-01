"""Stable public errors; preserve protocol headers, never exception text."""
from flask import g, jsonify
from werkzeug.exceptions import HTTPException

ERRORS = {
    404: ("NOT_FOUND", "Resource not found"),
    405: ("METHOD_NOT_ALLOWED", "Method not allowed"),
    500: ("INTERNAL_ERROR", "Internal server error"),
    503: ("DEPENDENCY_UNAVAILABLE", "Service temporarily unavailable"),
}


def error_response(status):
    code, message = ERRORS.get(status, ("HTTP_ERROR", "Request failed"))
    g.error_code = code
    response = jsonify(error={"code": code, "message": message, "details": {}},
                       request_id=g.request_id)
    response.status_code = status
    return response


def register_errors(app):
    @app.errorhandler(HTTPException)
    def handle_http(error):
        response = error_response(error.code)
        for name, value in error.get_response().headers:
            if name.lower() not in ("content-type", "content-length"):
                response.headers.add(name, value)
        return response

    @app.errorhandler(Exception)
    def handle_unexpected(_error):
        return error_response(500)
