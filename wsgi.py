"""WSGI entry point; configuration is loaded on application creation."""
from campus_repair import create_app

app = create_app()
