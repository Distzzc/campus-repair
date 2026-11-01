"""Gunicorn loads this file from the project working directory."""
import os
from campus_repair.logging_config import emit

bind = "0.0.0.0:8000"
workers = 1
timeout = 30
graceful_timeout = 10
preload_app = True
logger_class = "campus_repair.server_logging.JsonServerLogger"
accesslog = None
loglevel = os.environ.get("LOG_LEVEL", "INFO").lower()


def on_exit(server):
    emit("shutdown")
