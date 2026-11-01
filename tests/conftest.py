"""Scenario fixtures never consume a developer's environment or database."""
from pathlib import Path
import sqlite3

import pytest
from campus_repair import create_app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for name in ("APP_ENV", "DATABASE_PATH", "LOG_LEVEL", "DB_TIMEOUT_SECONDS", "COOKIE_SECURE", "DEMO_MODE", "DEMO_PASSWORD", "ADMIN_INVITE_CODE", "WORKER_INVITE_CODE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FLASK_SKIP_DOTENV", "1")


@pytest.fixture
def settings(tmp_path):
    path = tmp_path / "test.sqlite3"
    sqlite3.connect(path).close()
    return {"APP_ENV": "testing", "DATABASE_PATH": str(path), "DB_TIMEOUT_SECONDS": "1"}


@pytest.fixture
def app(settings):
    return create_app(settings)
