"""Explicit environment parsing; error messages never include input values."""
import os
from pathlib import Path
import re


class ConfigurationError(Exception):
    def __init__(self, code, field, rule):
        self.code, self.field, self.rule = code, field, rule
        super().__init__(f"{code}: {field}: {rule}")


def invalid(field, rule):
    return ConfigurationError("CONFIG_INVALID", field, rule)


def decimal_integer(value, field, minimum, maximum):
    rule = f"Expected decimal integer {minimum}..{maximum}"
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
        raise invalid(field, rule)
    # Bound input length before converting untrusted strings.
    if len(value) > 10 or not minimum <= int(value) <= maximum:
        raise invalid(field, rule)
    return int(value)


def load_config(overrides=None):
    names = ("APP_ENV", "DATABASE_PATH", "LOG_LEVEL", "DB_TIMEOUT_SECONDS")
    values = {name: os.environ[name] for name in names if name in os.environ}
    if overrides:
        values.update({key: val for key, val in overrides.items() if key in names})
    for field in ("APP_ENV", "DATABASE_PATH"):
        if field not in values or values[field] in ("", None):
            raise ConfigurationError("CONFIG_MISSING", field, "Required configuration")
    if values["APP_ENV"] not in ("development", "testing", "production"):
        raise invalid("APP_ENV", "Expected development, testing or production")
    raw_path = values["DATABASE_PATH"]
    rule = "Expected absolute .sqlite3 file and existing writable parent directory"
    if not isinstance(raw_path, str) or "\x00" in raw_path:
        raise invalid("DATABASE_PATH", rule)
    path = Path(raw_path)
    try:
        if (not path.is_absolute() or path.suffix != ".sqlite3"
                or not path.parent.is_dir() or not os.access(path.parent, os.W_OK)
                or not path.parent.stat().st_mode & 0o222
                or (path.exists() and not path.is_file())):
            raise invalid("DATABASE_PATH", rule)
    except OSError:
        raise invalid("DATABASE_PATH", rule) from None
    level = values.get("LOG_LEVEL", "INFO")
    if level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        raise invalid("LOG_LEVEL", "Expected DEBUG, INFO, WARNING or ERROR")
    timeout = decimal_integer(values.get("DB_TIMEOUT_SECONDS", "2"),
                              "DB_TIMEOUT_SECONDS", 1, 10)
    return {"APP_ENV": values["APP_ENV"], "DATABASE_PATH": str(path),
            "LOG_LEVEL": level, "DB_TIMEOUT_SECONDS": timeout}
