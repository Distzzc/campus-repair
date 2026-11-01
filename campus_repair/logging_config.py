"""Allowlisted JSON events, independent of app instances and global handlers."""
from datetime import datetime, timezone
import json
import logging
import sys
from time import monotonic
from uuid import uuid4

from flask import g, request


def emit(event, level="INFO", minimum_level="DEBUG", **fields):
    if logging.getLevelName(level) < logging.getLevelName(minimum_level):
        return
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "level": level, "event": event, "request_id": None,
        "method": None, "path": None, "status_code": None, "duration_ms": None,
    }
    # No arbitrary exception/message/input values can reach this serializer.
    record.update({key: value for key, value in fields.items() if key in {
        "request_id", "method", "path", "status_code", "duration_ms", "error_code", "field", "rule"
    }})
    print(json.dumps(record, ensure_ascii=False, separators=(",", ":")), file=sys.stdout, flush=True)


class SanitizedHandler(logging.Handler):
    def emit(self, record):
        emit("framework_event", record.levelname)


def configure_requests(app):
    logger = logging.Logger(f"campus_repair.{id(app)}", level=app.config["LOG_LEVEL"])
    logger.addHandler(SanitizedHandler())
    logger.propagate = False
    app.logger = logger

    @app.before_request
    def begin_request():
        g.request_id = str(uuid4())
        g.request_started = monotonic()

    @app.after_request
    def finish_request(response):
        response.headers["X-Request-ID"] = g.request_id
        status = response.status_code
        level = "WARNING" if status == 503 or 400 <= status < 500 else "ERROR" if status >= 500 else "INFO"
        fields = {"request_id": g.request_id, "method": request.method,
                  "path": request.url_rule.rule if request.url_rule else "<unmatched>",
                  "status_code": status,
                  "duration_ms": round(max(0, monotonic() - g.request_started) * 1000, 3)}
        if getattr(g, "error_code", None):
            fields["error_code"] = g.error_code
        emit("request_completed", level, **fields)
        return response
