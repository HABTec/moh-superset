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
# Production HTTPS enforcement — set in your systemd EnvironmentFile:
#   MOH_FORCE_HTTPS=true   (default) — enforces HTTPS + secure cookies
#   MOH_FORCE_HTTPS=false  — disable when TLS is terminated upstream (load balancer)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Database (metadata store) — Postgres recommended for production
# ---------------------------------------------------------------------------
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "SUPERSET_DATABASE_URI",
    "postgresql://superset:root@localhost:5432/superset",
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

# Cache, results backend, and async query settings are defined in
# superset/moh_branding.py (imported below) using the same SUPERSET_REDIS_*
# env vars. Redis DB assignments:
#   DB 0 — Celery broker
#   DB 1 — CACHE_CONFIG (UI/metadata)
#   DB 2 — DATA_CACHE_CONFIG (chart query results)
#   DB 3 — THUMBNAIL_CACHE_CONFIG
#   DB 4 — GLOBAL_ASYNC_QUERIES state
#   DB 5 — RESULTS_BACKEND (SQL Lab)
#   DB 6 — Celery task result_backend

# ---------------------------------------------------------------------------
# Celery — for alerts, scheduled reports, async SQL Lab, thumbnails
# Run a worker:  celery -A superset.tasks.celery_app:app worker -O fair -c 4
# Run beat:      celery -A superset.tasks.celery_app:app beat
# ---------------------------------------------------------------------------
from celery.schedules import crontab  # noqa: E402


class CeleryConfig:  # noqa: D101
    broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
    result_backend = f"redis://{REDIS_HOST}:{REDIS_PORT}/6"
    imports = (
        "superset.sql_lab",
        "superset.tasks.scheduler",
        "superset.tasks.thumbnails",
        "superset.tasks.cache",
    )
    worker_prefetch_multiplier = 1
    task_acks_late = False
    # WITHOUT "reports.scheduler" running every minute, Alerts & Reports never
    # fire. Requires `celery ... beat` to be running.
    beat_schedule = {
        "reports.scheduler": {
            "task": "reports.scheduler",
            "schedule": crontab(minute="*", hour="*"),
        },
        "reports.prune_log": {
            "task": "reports.prune_log",
            "schedule": crontab(minute=0, hour=0),
        },
    }


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
