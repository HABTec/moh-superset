# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.
import pytest

from superset.moh_ai_insights import (
    _ask_llm,
    _generate_demo_insight,
    _generate_insight,
    _insights_enabled,
)


def test_generate_demo_insight_uses_stats_and_trend() -> None:
    summary = {
        "row_count": 12,
        "columns": ["period", "visits"],
        "numeric_stats": [
            {"column": "visits", "min": 40.0, "max": 480.0, "avg": 150.0}
        ],
        "trend": {
            "column": "visits",
            "direction": "increasing",
            "start": 40.0,
            "end": 480.0,
            "first_label": "2025-01",
            "last_label": "2026-08",
        },
        "top_values": [
            {
                "column": "region",
                "values": [{"value": "AA", "count": 6}],
                "total": 12,
            }
        ],
    }
    insight = _generate_demo_insight(summary, [])
    assert "12 rows" in insight
    assert "ranges from 40 to 480" in insight
    assert "increased from 40 to 480" in insight
    assert "AA" in insight


def test_generate_demo_insight_empty_data() -> None:
    insight = _generate_demo_insight({}, [])
    assert "no data" in insight


def test_generate_insight_falls_back_to_demo_without_credentials(monkeypatch) -> None:
    monkeypatch.delenv("MOH_AI_INSIGHTS_API_KEY", raising=False)
    monkeypatch.delenv("MOH_AI_INSIGHTS_PROVIDER", raising=False)
    result = _generate_insight(
        chart_id=1,
        chart_name="OPD visits",
        viz_type="line",
        summary={"row_count": 5},
        sample_rows=[{"period": "2025-01", "visits": 100}],
    )
    assert result["provider"] == "demo"
    assert isinstance(result["insight"], str)


def test_ask_llm_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        _ask_llm("works", "key", "model", "prompt", 1)


def test_insights_enabled_parses_strings(monkeypatch) -> None:
    monkeypatch.setenv("MOH_AI_INSIGHTS_ENABLED", "false")
    assert _insights_enabled() is False
    monkeypatch.setenv("MOH_AI_INSIGHTS_ENABLED", "true")
    assert _insights_enabled() is True