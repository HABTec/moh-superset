# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""
AI insights for dashboard charts — a compact per-chart narrative shown beside
each chart in the Health Intelligence dashboard.

POST /ai-insights/chart/<chart_id>/
    Accepts a small JSON payload summarised client-side from the chart's latest
    query results (the frontend already has the data, so no query is re-run
    server-side):

        {
          "chart_id": 153,
          "chart_name": "OPD attendance by woreda",
          "viz_type": "echarts_timeseries_bar",
          "dashboard_id": 8,
          "summary": {
            "row_count": 231,
            "columns": ["period", "value"],
            "numeric_stats": [
              {"column": "value", "min": 12.0, "max": 480.0,
               "avg": 156.4, "count": 231}
            ],
            "top_values": [
              {"column": "ow", "values": [{"value": "AA", "count": 44}],
               "total": 120}
            ],
            "trend": {
              "column": "value", "direction": "increasing",
              "start": 41.0, "end": 388.0,
              "first_label": "2025-01", "last_label": "2026-08"
            }
          },
          "sample_rows": [{"period": "2025-01", "value": 41.0}]
        }

    The insight is generated with a real LLM provider (openai | gemini |
    claude) when MOH_AI_INSIGHTS_PROVIDER and MOH_AI_INSIGHTS_API_KEY are
    configured, otherwise a deterministic template-based generator runs so the
    feature works without any external credentials (hybrid mode).

    Responses are cached in-process keyed on (chart id + payload hash) so
    re-renders after a data refresh do not re-pay the LLM cost.

Registered with Flask via the BLUEPRINTS list in superset_config.py — no
edits to upstream Superset init code.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any

import requests
from flask import Blueprint, current_app, has_app_context, jsonify, request
from flask_login import login_required

from superset.superset_typing import FlaskResponse

logger = logging.getLogger(__name__)

ai_insights_bp = Blueprint("moh_ai_insights", __name__)

# In-process cache: cache_key -> (expiry_ts, payload). Small enough for a
# single-instance deploy; swap for Redis if the app is scaled horizontally.
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

_MAX_SAMPLE_ROWS = 40
_MAX_LLM_TEXT_CHARS = 6000
_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "claude": "claude-3-5-haiku-latest",
}

_PROVIDER_ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/models/"
               "{model}:generateContent"),
    "claude": "https://api.anthropic.com/v1/messages",
}


def _config(name: str, default: object = "") -> object:
    """Read from Flask config first, then fall back to the environment."""
    if has_app_context() and current_app.config.get(name) is not None:
        return current_app.config.get(name, default)
    return os.environ.get(name, default)


def _int_config(name: str, default: int) -> int:
    try:
        return int(str(_config(name, default)))
    except (TypeError, ValueError):
        return default


def _provider() -> str:
    return str(_config("MOH_AI_INSIGHTS_PROVIDER", "")).strip().lower()


def _api_key() -> str:
    return str(_config("MOH_AI_INSIGHTS_API_KEY", "")).strip()


def _model() -> str:
    value = str(_config("MOH_AI_INSIGHTS_MODEL", "")).strip()
    if value:
        return value
    return _DEFAULT_MODELS.get(_provider(), "")


def _timeout() -> int:
    return _int_config("MOH_AI_INSIGHTS_TIMEOUT", 20)


def _cache_ttl() -> int:
    return _int_config("MOH_AI_INSIGHTS_CACHE_TTL", 300)


def _insights_enabled() -> bool:
    raw = _config("MOH_AI_INSIGHTS_ENABLED", True)
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return bool(raw)


# ---------------------------------------------------------------------------
# Deterministic, template-based generator (the "demo" provider)
# ---------------------------------------------------------------------------

def _format_number(value: float | int | None) -> str:
    if value is None:
        return "?"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "?"
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.1f}"


def _direction_word(direction: str) -> str:
    return {
        "increasing": "increased",
        "decreasing": "decreased",
        "stable": "stayed roughly level",
    }.get(direction, "trended")


def _generate_demo_insight(summary: dict[str, Any], sample_rows: list[Any]) -> str:
    """Build a deterministic 2-4 sentence insight from a compact summary."""
    sentences: list[str] = []

    columns = summary.get("columns") or []
    row_count = summary.get("row_count")
    if isinstance(row_count, (int, float)):
        noun = "row" if int(row_count) == 1 else "rows"
        cols_txt = f" across {len(columns)} columns" if columns else ""
        sentences.append(
            f"This chart covers {row_count:,} {noun} of data{cols_txt}."
        )

    numeric_stats = summary.get("numeric_stats") or []
    if isinstance(row_count, (int, float)) or numeric_stats:
        for stat in numeric_stats[:2]:
            column = stat.get("column", "value")
            metric_range = (
                f"ranges from {_format_number(stat.get('min'))} to "
                f"{_format_number(stat.get('max'))}"
            )
            avg = stat.get("avg")
            avg_txt = (
                f" with an average of {_format_number(avg)}" if avg is not None else ""
            )
            sentences.append(f"{column.capitalize()} {metric_range}{avg_txt}.")

    trend = summary.get("trend") or {}
    if trend.get("direction") and trend.get("column"):
        start = _format_number(trend.get("start"))
        end = _format_number(trend.get("end"))
        first = trend.get("first_label")
        last = trend.get("last_label")
        period_txt = (
            f" from {first} to {last}" if first is not None and last is not None else ""
        )
        sentences.append(
            f"Over the period{period_txt}, {trend.get('column')} {_direction_word(str(trend.get('direction')))} "
            f"from {start} to {end}."
        )

    top_values = summary.get("top_values") or []
    for top in top_values[:1]:
        values = top.get("values") or []
        if values:
            leader = values[0]
            total = top.get("total")
            pct = (
                f" ({int(leader.get('count', 0)) / int(total) * 100:.0f}% of all records)"
                if total else ""
            )
            sentences.append(
                f"The leading {top.get('column', 'category')} is {leader.get('value')} "
                f"with {leader.get('count')} records{pct}."
            )

    if not sentences:
        sentences.append(
            "This chart returned no data. Check the active filters or refresh the dashboard."
        )

    return " ".join(sentences)


# ---------------------------------------------------------------------------
# LLM providers
# ---------------------------------------------------------------------------

def _build_llm_prompt(
    chart_name: str,
    viz_type: str,
    summary: dict[str, Any],
    sample_rows: list[Any],
) -> str:
    compact = json.dumps(
        summary, sort_keys=True, default=str, ensure_ascii=True
    )
    prompt = (
        "You are an expert public-health data analyst writing a short AI insight "
        "for a chart inside a Ministry of Health dashboard.\n\n"
        f"Chart name: {chart_name}\n"
        f"Chart type: {viz_type}\n\n"
        f"Summary of the latest query:\n{compact}\n\n"
        f"Sample rows (first {len(sample_rows)}):\n"
        f"{json.dumps(sample_rows, sort_keys=True, default=str, ensure_ascii=True)}\n\n"
        "Write 2-4 concise sentences on the most notable patterns, outliers, and "
        "implications for health decision-makers. Plain text only, no markdown, "
        "no headings."
    )
    return prompt


def _ask_openai(prompt: str, api_key: str, model: str, timeout: int) -> str:
    resp = requests.post(
        _PROVIDER_ENDPOINTS["openai"],
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You produce concise, accurate data insights.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 250,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return str(resp.json()["choices"][0]["message"]["content"]).strip()


def _ask_gemini(prompt: str, api_key: str, model: str, timeout: int) -> str:
    url = _PROVIDER_ENDPOINTS["gemini"].format(model=model)
    resp = requests.post(
        url,
        params={"key": api_key},
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ]
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    parts = resp.json()["candidates"][0]["content"]["parts"]
    return "".join(part.get("text", "") for part in parts).strip()


def _ask_claude(prompt: str, api_key: str, model: str, timeout: int) -> str:
    resp = requests.post(
        _PROVIDER_ENDPOINTS["claude"],
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": model,
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    chunks = resp.json().get("content") or []
    return "".join(
        str(part.get("text", ""))
        for part in chunks
        if isinstance(part, dict) and part.get("type") == "text"
    ).strip()


def _ask_llm(
    provider: str,
    api_key: str,
    model: str,
    prompt: str,
    timeout: int,
) -> str:
    if provider == "openai":
        return _ask_openai(prompt, api_key, model, timeout)
    if provider == "gemini":
        return _ask_gemini(prompt, api_key, model, timeout)
    if provider in {"claude", "anthropic"}:
        return _ask_claude(prompt, api_key, model, timeout)
    raise ValueError(f"Unsupported AI insights provider: {provider}")


# ---------------------------------------------------------------------------
# Main generator with caching + hybrid fallback
# ---------------------------------------------------------------------------

def _cache_key(chart_id: int, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"moh_ai_insights:{chart_id}:{digest}"


def _generate_insight(
    chart_id: int,
    chart_name: str,
    viz_type: str,
    summary: dict[str, Any],
    sample_rows: list[Any],
) -> dict[str, Any]:
    """Return {insight, provider} — LLM when configured, else demo templates."""
    provider = _provider()
    api_key = _api_key()

    if provider in _PROVIDER_ENDPOINTS and api_key:
        prompt = _build_llm_prompt(chart_name, viz_type, summary, sample_rows)
        try:
            insight = _ask_llm(
                provider,
                api_key,
                _model(),
                prompt,
                _timeout(),
            )
            if insight:
                return {"insight": insight, "provider": provider}
        except Exception:  # noqa: BLE001 - fall back to demo on any LLM failure
            logger.warning(
                "AI insights LLM call failed for chart %s (%s); using demo "
                "fallback",
                chart_id,
                provider,
                exc_info=True,
            )

    return {"insight": _generate_demo_insight(summary, sample_rows), "provider": "demo"}


@ai_insights_bp.route("/ai-insights/chart/<int:chart_id>/", methods=["POST"])
@login_required
def generate_chart_insight(chart_id: int) -> FlaskResponse:
    """Generate (and cache) an AI insight for one chart on a dashboard.

    ---
    post:
      summary: Generate an AI insight for a dashboard chart
      parameters:
      - name: chart_id
        in: path
        required: true
        schema: {type: integer}
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                chart_name: {type: string}
                viz_type: {type: string}
                dashboard_id: {type: integer}
                summary: {type: object}
                sample_rows: {type: array}
      responses:
        200:
          description: Generated insight
          content:
            application/json:
              schema:
                type: object
                properties:
                  chart_id: {type: integer}
                  chart_name: {type: string}
                  dashboard_id: {type: integer}
                  insight: {type: string}
                  provider: {type: string}
                  generated_at: {type: string}
                  cached: {type: boolean}
        404:
          description: AI insights are disabled
    """
    if not _insights_enabled():
        return jsonify({"error": "AI insights are disabled"}), 404

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON payload"}), 400

    chart_name = str(payload.get("chart_name") or "Chart").strip()
    viz_type = str(payload.get("viz_type") or "chart").strip()
    dashboard_id = payload.get("dashboard_id")
    summary = payload.get("summary")
    sample_rows = payload.get("sample_rows")

    if not isinstance(summary, dict):
        return jsonify({"error": "Missing chart data summary"}), 400

    if sample_rows is None:
        sample_rows = []
    try:
        sample_rows = sample_rows[:_MAX_SAMPLE_ROWS]
        summary = json.loads(
            json.dumps(summary, default=str)[:_MAX_LLM_TEXT_CHARS]
        )
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid summary payload"}), 400

    request_payload = {
        "chart_name": chart_name,
        "viz_type": viz_type,
        "summary": summary,
        "sample_rows": sample_rows,
    }
    cache_key = _cache_key(chart_id, request_payload)
    now = time.time()

    cached = _CACHE.get(cache_key)
    if cached and cached[0] > now:
        return jsonify({**cached[1], "cached": True})

    result = _generate_insight(
        chart_id,
        chart_name,
        viz_type,
        summary,
        sample_rows,
    )
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    response_payload = {
        "chart_id": chart_id,
        "chart_name": chart_name,
        "dashboard_id": dashboard_id,
        "insight": result["insight"],
        "provider": result["provider"],
        "generated_at": generated_at,
        "cached": False,
    }
    _CACHE[cache_key] = (now + _cache_ttl(), response_payload)
    return jsonify(response_payload)