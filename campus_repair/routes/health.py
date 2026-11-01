"""Public readiness endpoint; no business rules or authentication."""
import sqlite3
from flask import Blueprint, g, jsonify
from campus_repair.db import get_db, probe
from campus_repair.errors import error_response

blueprint = Blueprint("health", __name__)


@blueprint.get("/health")
def health():
    try:
        probe(get_db())
    except (sqlite3.Error, OSError):
        return error_response(503)
    return jsonify(status="ok", checks={"database": "ok"}, request_id=g.request_id)
