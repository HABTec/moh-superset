# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.
"""
Native (non-Docker) Superset configuration TEMPLATE for the MoH deployment.

This is a checked-in template. On a fresh Ubuntu install:

    cp superset_config.example.py superset_config.py
    # edit superset_config.py if needed (it already reads secrets from env)
    export SUPERSET_CONFIG_PATH=/abs/path/to/moh-superset/superset_config.py

Apache's .gitignore deliberately excludes /superset_config.py at the project
root so locally-edited copies (with hardcoded secrets) cannot accidentally be
committed. This template is safe to commit because it pulls every secret from
environment variables.

Docker dev compose uses `docker/pythonpath_dev/superset_config.py` instead and
does NOT load this file.

Sensitive values (DB password, SECRET_KEY) come from environment variables —
never commit secrets here. Suggested .env or systemd Environment= lines:

    SUPERSET_DATABASE_URI=postgresql://superset:STRONG_PW@localhost:5432/superset
    SUPERSET_SECRET_KEY=<output of: python -c "import secrets; print(secrets.token_urlsafe(42))">
    SUPERSET_REDIS_HOST=localhost
    SUPERSET_REDIS_PORT=6379
"""

import os

# ---------------------------------------------------------------------------
# Database (metadata store) — Postgres recommended for production
# ---------------------------------------------------------------------------
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "SUPERSET_DATABASE_URI",
    "postgresql://superset:CHANGE_ME@localhost:5432/superset",
)

# ---------------------------------------------------------------------------
# Secrets — REQUIRED in production. Generate with:
#     python -c "import secrets; print(secrets.token_urlsafe(42))"
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    "SUPERSET_SECRET_KEY",
    "CHANGE_ME_in_production_or_set_SUPERSET_SECRET_KEY_env_var",
)

# ---------------------------------------------------------------------------
# Redis (cache + Celery broker)
# ---------------------------------------------------------------------------
REDIS_HOST = os.environ.get("SUPERSET_REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("SUPERSET_REDIS_PORT", "6379"))

CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": 1,
}
DATA_CACHE_CONFIG = CACHE_CONFIG
THUMBNAIL_CACHE_CONFIG = CACHE_CONFIG

# Stores SQL Lab query results on the local filesystem. Override RESULTS_BACKEND
# for distributed deploys (e.g. S3, GCS).
from flask_caching.backends.filesystemcache import FileSystemCache  # noqa: E402

RESULTS_BACKEND = FileSystemCache(
    os.environ.get("SUPERSET_RESULTS_DIR", "/var/lib/superset/sqllab")
)

# ---------------------------------------------------------------------------
# Celery — for alerts, scheduled reports, async SQL Lab, thumbnails
# Run a worker:  celery -A superset.tasks.celery_app:app worker -O fair -c 4
# Run beat:      celery -A superset.tasks.celery_app:app beat
# ---------------------------------------------------------------------------
class CeleryConfig:  # noqa: D101
    broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
    result_backend = f"redis://{REDIS_HOST}:{REDIS_PORT}/1"
    imports = (
        "superset.sql_lab",
        "superset.tasks.scheduler",
        "superset.tasks.thumbnails",
        "superset.tasks.cache",
    )
    worker_prefetch_multiplier = 1
    task_acks_late = False


CELERY_CONFIG = CeleryConfig

# ---------------------------------------------------------------------------
# Logging level — DEBUG for first-run troubleshooting, INFO/WARNING in prod
# ---------------------------------------------------------------------------
import logging  # noqa: E402

LOG_LEVEL = getattr(
    logging, os.environ.get("SUPERSET_LOG_LEVEL", "INFO").upper(), logging.INFO
)

# ---------------------------------------------------------------------------
# MoH customizations — single source of truth: superset/moh_branding.py
# Pulls in VERSION_STRING, APP_NAME, APP_ICON, THEME_DEFAULT, THEME_DARK,
# FEATURE_FLAGS, and any other branding/theming we add over time.
# ---------------------------------------------------------------------------
from superset.moh_branding import *  # noqa: E402,F401,F403
