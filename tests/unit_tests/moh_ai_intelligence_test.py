# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements. See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership. The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

from superset.moh_ai_intelligence import (
    _build_intent_prompt,
    _candidate_charts,
    _intelligence_model,
    _parse_intent,
    _validated_filters,
)


def test_intelligence_model_uses_its_own_environment_override(monkeypatch) -> None:
    monkeypatch.setenv("MOH_AI_INTELLIGENCE_MODEL", "gemini-3.6-flash")

    assert _intelligence_model("gemini-1.5-flash") == "gemini-3.6-flash"


def test_intelligence_model_falls_back_when_override_is_empty(monkeypatch) -> None:
    monkeypatch.setenv("MOH_AI_INTELLIGENCE_MODEL", "")

    assert _intelligence_model("gemini-1.5-flash") == "gemini-1.5-flash"


def test_candidate_charts_ranks_by_question_terms() -> None:
    charts = [
        (
            None,
            {
                "id": 1,
                "name": "ANC coverage by region",
                "description": "Coverage trend",
                "dataset": "health indicators",
                "columns": ["region", "year"],
            },
        ),
        (
            None,
            {
                "id": 2,
                "name": "Facility counts",
                "description": "Facility totals by region",
                "dataset": "facilities",
                "columns": ["region"],
            },
        ),
    ]

    result = _candidate_charts("ANC coverage for 2024", charts)

    assert [chart["id"] for chart in result] == [1]
    assert result[0]["confidence"] == 67
    assert result[0]["matched_terms"] == ["anc", "coverage"]


def test_selected_chart_prompt_only_extracts_filters_for_that_chart() -> None:
    prompt = _build_intent_prompt(
        "Show ANC coverage in 2018",
        [{"id": 12, "name": "ANC coverage", "columns": ["year"]}],
        selected_chart_id=12,
    )

    assert "explicitly selected" in prompt
    assert "Do not ask which chart" in prompt
    assert "Show ANC coverage in 2018" in prompt


def test_parse_intent_accepts_structured_response() -> None:
    text = json.dumps(
        {
            "chart_id": 12,
            "filters": [{"column": "region", "value": "Amhara"}],
            "needs_clarification": False,
        }
    )

    assert _parse_intent(text) == json.loads(text)


def test_parse_intent_rejects_non_integer_chart_id() -> None:
    text = json.dumps(
        {
            "chart_id": "12",
            "filters": [],
            "needs_clarification": False,
        }
    )

    assert _parse_intent(text) is None


def test_validated_filters_only_accept_chart_columns() -> None:
    intent = {
        "filters": [
            {"column": "region", "value": "Amhara"},
            {"column": "private_note", "value": "secret"},
        ]
    }

    assert (
        _validated_filters(
            intent,
            {"columns": ["region", "year"]},
            "Amhara and secret",
        )
        is None
    )


def test_validated_filters_creates_fixed_in_operator() -> None:
    intent = {"filters": [{"column": "region", "value": "Amhara"}]}

    assert _validated_filters(intent, {"columns": ["region"]}, "for Amhara") == [
        {"col": "region", "op": "IN", "val": ["Amhara"]}
    ]
