"""Sanitize Gunicorn messages, including boot errors and untrusted request data."""
from gunicorn.glogging import Logger
from campus_repair.logging_config import emit


class JsonServerLogger(Logger):
    def setup(self, cfg):
        # No default text handlers, access log, or exception traceback.
        self.cfg = cfg

    def critical(self, msg, *args, **kwargs):
        emit("server_event", "ERROR", minimum_level=self.cfg.loglevel.upper())

    def error(self, msg, *args, **kwargs):
        emit("server_event", "ERROR", minimum_level=self.cfg.loglevel.upper())

    def warning(self, msg, *args, **kwargs):
        emit("server_event", "WARNING", minimum_level=self.cfg.loglevel.upper())

    def info(self, msg, *args, **kwargs):
        emit("server_event", minimum_level=self.cfg.loglevel.upper())

    def debug(self, msg, *args, **kwargs):
        if self.cfg.loglevel == "debug":
            emit("server_event", "DEBUG", minimum_level=self.cfg.loglevel.upper())

    def exception(self, msg, *args, **kwargs):
        emit("server_event", "ERROR", minimum_level=self.cfg.loglevel.upper())

    def access(self, resp, req, environ, request_time):
        pass  # The application emits exactly one allowlisted completion event.

    def reopen_files(self):
        pass

    def close_on_exec(self):
        pass
