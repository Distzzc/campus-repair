FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS production
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FLASK_SKIP_DOTENV=1 PYTHONPATH=/app
WORKDIR /app
COPY requirements.lock ./
RUN python -m pip install --no-cache-dir -r requirements.lock \
    && groupadd --gid 10001 campus \
    && useradd --uid 10001 --gid 10001 --no-create-home campus
COPY campus_repair/ ./campus_repair/
COPY wsgi.py gunicorn.conf.py ./
COPY scripts/ ./scripts/
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]

FROM production AS test
USER root
COPY requirements-dev.lock pyproject.toml ./
RUN python -m pip install --no-cache-dir -r requirements-dev.lock
COPY tests/ ./tests/
COPY README.md AGENTS.md .env.example .gitignore .dockerignore ./
COPY docs/ ./docs/
COPY openspec/ ./openspec/
USER 10001:10001
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
