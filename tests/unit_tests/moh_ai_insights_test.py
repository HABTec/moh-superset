# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.
import json

import pytest

from superset.moh_ai_insights import (
    _ask_llm,
    _bounded_summary,
    _cap_strings,
    _generate_demo_insight,
    _generate_insight,
    _insights_enabled,
    _parse_llm_insight,
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
    assert isinstance(insight["summary"], str)
    assert isinstance(insight["bullets"], list)
    assert "12 rows" in insight["summary"]
    assert any(
        "ranges from 40 to 480" in bullet for bullet in insight["bullets"]
    )
    assert any(
        "increased from 40 to 480" in bullet for bullet in insight["bullets"]
    )
    assert any("AA" in bullet for bullet in insight["bullets"])


def test_generate_demo_insight_empty_data() -> None:
    insight = _generate_demo_insight({}, [])
    assert "no data" in insight["summary"]
    assert insight["bullets"] == []


def test_generate_demo_insight_accepts_camelcase_keys() -> None:
    summary = {
        "rowCount": 56,
        "columns": ["region", "AVG(deaths)"],
        "numericStats": [
            {"column": "AVG(deaths)", "min": 2.0, "max": 89.0, "avg": 23.5}
        ],
        "topValues": [
            {
                "column": "region",
                "values": [{"value": "Oromia", "count": 12}],
                "total": 56,
            }
        ],
    }
    insight = _generate_demo_insight(summary, [])
    assert "56 rows" in insight["summary"]
    assert any(
        "ranges from 2 to 89" in bullet for bullet in insight["bullets"]
    )
    assert any("Oromia" in bullet for bullet in insight["bullets"])


def test_generate_demo_insight_skips_structural_columns() -> None:
    summary = {
        "rowCount": 926,
        "columns": ["geometry_geojson", "region"],
        "numeric_stats": [],
        "topValues": [
            {
                "column": "geometry_geojson",
                "values": [{"value": "[[[", "count": 1}],
                "total": 926,
            },
            {
                "column": "region",
                "values": [{"value": "Oromia", "count": 180}],
                "total": 926,
            },
        ],
    }
    insight = _generate_demo_insight(summary, [])
    assert "geometry_geojson" not in insight["summary"]
    assert all("geometry_geojson" not in bullet for bullet in insight["bullets"])
    assert any("Oromia" in bullet for bullet in insight["bullets"])


def test_cap_strings_trims_long_values() -> None:
    capped = _cap_strings({"value": "x" * 500, "nested": {"y": "z" * 5_000}}, 100)
    assert len(capped["value"]) == 100
    assert len(capped["nested"]["y"]) == 100
    assert _cap_strings(3) == 3
    assert _cap_strings(["ab"]) == ["ab"]


def test_bounded_summary_stays_valid_and_small() -> None:
    giant = "[" * 10_000
    summary = {
        "rowCount": 926,
        "columns": ["geometry_geojson"] * 500,
        "numericStats": [{"column": f"m{i}", "min": i} for i in range(500)],
        "topValues": [
            {"column": f"c{i}", "values": [{"value": giant, "count": 1}]}
            for i in range(200)
        ],
        "trend": None,
    }
    bounded = _bounded_summary(summary)
    assert isinstance(bounded, dict)
    assert json.loads(json.dumps(bounded)) == bounded
    assert len(json.dumps(bounded)) <= 6000
    assert all(
        isinstance(v.get("values"), list) and len(v["values"]) <= 3
        for v in bounded["topValues"]
    )


def test_bounded_summary_normalizes_keys() -> None:
    bounded = _bounded_summary(
        {"row_count": 5, "colnames": ["a"], "numeric_stats": []}
    )
    assert bounded["rowCount"] == 5
    assert bounded["columns"] == ["a"]
    assert bounded["numericStats"] == []


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
    assert isinstance(result["summary"], str)
    assert isinstance(result["bullets"], list)


def test_parse_llm_insight_parses_json() -> None:
    parsed = _parse_llm_insight(
        '{"summary": "Headline takeaway.", '
        '"bullets": ["one", "", "three", "four", "five"]}'
    )
    assert parsed == {
        "summary": "Headline takeaway.",
        "bullets": ["one", "three", "four", "five"],
    }


def test_parse_llm_insight_tolerates_markdown_fence() -> None:
    parsed = _parse_llm_insight(
        '```json\n{"summary": "Headline.", "bullets": ["a", "b"]}\n```'
    )
    assert parsed == {"summary": "Headline.", "bullets": ["a", "b"]}


def test_parse_llm_insight_returns_none_for_invalid_shape() -> None:
    assert _parse_llm_insight("not json at all") is None
    assert _parse_llm_insight('{"summary": 3}') is None
    assert _parse_llm_insight('{"summary": "x"}') is None


def test_ask_llm_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        _ask_llm("works", "key", "model", "prompt", 1)


def test_insights_enabled_parses_strings(monkeypatch) -> None:
    monkeypatch.setenv("MOH_AI_INSIGHTS_ENABLED", "false")
    assert _insights_enabled() is False
    monkeypatch.setenv("MOH_AI_INSIGHTS_ENABLED", "true")
    assert _insights_enabled() is True