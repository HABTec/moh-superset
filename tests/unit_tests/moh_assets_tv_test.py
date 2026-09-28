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
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from superset.moh_assets import (
    _render_tv_page,
    _tv_page_payload,
    _tv_slide_payload,
    DEFAULT_TV_EMPTY_MARKERS,
    default_tv_theme,
    tv_embed_url,
    tv_slide_accent,
    tv_slide_source,
)
from superset.utils import json

SLIDES = {
    "dashboard": "/superset/dashboard/8/?standalone=2",
    "slides": [{"path": ["Services Delivery", "NCD"], "label": "NCD"}],
}


def test_default_tv_theme_uses_the_type_tokens() -> None:
    theme = default_tv_theme({"tv_size_floor": 22, "tv_size_chart": 24})

    assert theme["token"]["fontSize"] == 22
    assert theme["token"]["colorPrimary"] == "#0374B8"
    assert theme["token"]["colorTextTertiary"] == "#626B77"
    assert theme["token"]["colorWarning"] == "#8F5D00"
    overrides = theme["echartsOptionsOverrides"]
    assert overrides["textStyle"]["fontSize"] == 24
    assert overrides["legend"]["textStyle"]["fontSize"] == 24
    assert overrides["xAxis"]["axisLabel"] == {"fontSize": 24, "hideOverlap": True}
    assert overrides["yAxis"]["axisLabel"]["fontSize"] == 24


def test_default_tv_theme_keeps_time_axis_labels_upright_and_thinned() -> None:
    theme = default_tv_theme({"tv_size_chart": 26})

    axis = theme["echartsOptionsOverridesByChartType"]["echarts_timeseries"]["xAxis"]
    assert axis["axisLabel"]["rotate"] == 0
    assert axis["axisLabel"]["hideOverlap"] is True
    assert axis["axisLabel"]["fontSize"] == 26


def test_default_tv_theme_falls_back_to_the_legibility_floor() -> None:
    theme = default_tv_theme(None)

    assert theme["token"]["fontSize"] == 22
    assert theme["echartsOptionsOverrides"]["textStyle"]["fontSize"] == 24


def test_payload_carries_the_shell_options() -> None:
    options = {"canvas": {"width": 1920, "height": 1080}, "skipEmptyRatio": 0.8}

    payload = _tv_page_payload(SLIDES, 40, 120, options)

    assert payload["intervalMs"] == 40_000
    assert payload["reloadMinutes"] == 120
    assert payload["canvas"] == {"width": 1920, "height": 1080}
    assert payload["skipEmptyRatio"] == 0.8
    assert payload["slides"] == [
        {
            "path": ["Services Delivery", "NCD"],
            "label": "NCD",
            "accent": "#1F7A6C",
            "source": "DHIS2 · Routine",
        }
    ]


def test_payload_without_options_matches_the_previous_shape() -> None:
    payload = _tv_page_payload(SLIDES, 40, 120)

    assert set(payload) == {"url", "slides", "intervalMs", "reloadMinutes"}


def test_rendered_page_embeds_the_theme_as_json() -> None:
    theme = default_tv_theme({"tv_size_floor": 22, "tv_size_chart": 24})
    html = _render_tv_page(_tv_page_payload(SLIDES, 40, 120, {"theme": theme}))

    match = re.search(r"const CFG = (\{.*?\});\n", html, re.S)
    assert match is not None
    assert json.loads(match.group(1))["theme"] == theme


def test_rendered_page_cannot_be_broken_out_of_by_a_slide_label() -> None:
    slides = {
        "dashboard": "/x",
        "slides": [{"path": ["A"], "label": "</script><script>alert(1)</script>"}],
    }

    html = _render_tv_page(_tv_page_payload(slides, 40, 120))

    assert "</script><script>alert(1)" not in html


def test_tv_embed_url_opens_the_dashboard_in_the_same_window() -> None:
    url = tv_embed_url("/superset/dashboard/8/?standalone=2", "group-service-delivery")

    assert url.startswith("/superset/dashboard/8/")
    assert "standalone=2" in url
    assert "expand_filters=false" in url
    assert "moh_tv=group-service-delivery" in url
    assert "?_tv=" not in url and "&_tv=" not in url


def test_tv_slide_source_follows_the_module_then_an_explicit_override() -> None:
    assert tv_slide_source("NCD", ["Services Delivery", "NCD"]) == "DHIS2 · Routine"
    assert tv_slide_source("Health Equity") == "EDHS · Survey"
    assert tv_slide_source("Blood Donation") == "DHIS2 · Blood"
    assert tv_slide_source("PHEM") == "DHIS2 · Surveillance"
    assert (
        tv_slide_source("Blood Donation", explicit="NBTS · Blood bank")
        == "NBTS · Blood bank"
    )


def test_tv_slide_accent_uses_yengwe_module_hues() -> None:
    assert tv_slide_accent("NCD", ["Services Delivery", "NCD"]) == "#1F7A6C"
    assert tv_slide_accent("Maternal") == "#8B3A76"
    assert tv_slide_accent("Health Equity") == "#3B4E9B"
    assert tv_slide_accent("Unknown module") == "#0374B8"


def test_rendered_page_has_yengwe_chrome_and_hides_ask_ai() -> None:
    html = _render_tv_page(_tv_page_payload(SLIDES, 40, 120))

    assert 'id="mast"' in html
    assert 'id="strip"' in html
    assert "#05080B" in html
    assert ".moh-ai-overlay" in html
    assert "clipped, not scaled" in html
    assert "bounceToParentLogin" in html


PLAYER_PATH = (
    Path(__file__).resolve().parents[2]
    / "superset"
    / "templates"
    / "superset"
    / "moh_tv_player.js"
)


def _player() -> str:
    return PLAYER_PATH.read_text(encoding="utf-8")


def test_same_window_player_has_no_iframe() -> None:
    player = _player()

    assert "mohTvPanel" in player
    assert "tv-config/" in player
    assert "<iframe" not in player
    assert "header-title" in player
    assert "white-space:nowrap" in player
    assert "alignChartTitles" in player
    assert "sourcesFromChartTitles" in player
    assert "applyYear" in player
    assert "mohTvGregorian" not in player
    assert "G.C." not in player


def test_default_tv_theme_still_ships_24px_chart_text() -> None:
    theme = default_tv_theme(None)

    assert theme["echartsOptionsOverrides"]["legend"]["textStyle"]["fontSize"] == 24
    assert theme["echartsOptionsOverrides"]["yAxis"]["axisLabel"]["fontSize"] == 24


def test_default_empty_markers_cover_the_null_fallbacks() -> None:
    for marker in (
        "No results were returned for this query",
        "No data",
        "NULL",
        "No data after filtering",
        "Not available",
    ):
        assert marker in DEFAULT_TV_EMPTY_MARKERS


def test_slide_annotation_is_passed_through_only_when_set() -> None:
    bare = _tv_slide_payload({"path": ["A"], "label": "NCD"})
    noted = _tv_slide_payload(
        {"path": ["A"], "label": "NCD", "annotation": "  One sentence.  "}
    )

    assert "annotation" not in bare
    assert noted["annotation"] == "One sentence."


def test_player_reloads_once_so_the_theme_reaches_echarts() -> None:
    player = _player()

    assert "mohTvThemeApplied" in player
    assert "reloadKeepingTheme" in player
    assert "if (applyTheme(CFG.theme))" in player


def test_player_raises_chrome_roles_to_the_floor() -> None:
    player = _player()

    assert ".moh-tv-strip-k{font-size:22px;" in player
    assert "#mohTvMast .w2{font-size:22px;" in player
    assert "setImp(title, 'font-size', '24px')" in player
    assert "font-size:22px!important;font-weight:600" not in player
    assert "body.moh-tv-active.idle #mohTvControls{display:none!important;}" in player


def test_player_period_follows_the_cards_not_freshness() -> None:
    player = _player()
    fresh = player[player.index("function loadFreshness") :]
    fresh = fresh[: fresh.index("function setImp")]

    assert "yearFromCards" in player
    assert "applyYear" not in fresh


def test_player_skips_a_slide_whose_every_card_is_empty() -> None:
    player = _player()

    assert "dead === state.total" in player
    assert "skipStreak < CFG.slides.length - 1" in player


def _run_player_fn(fn_start: str, fn_end: str, call: str, prelude: str = "") -> str:
    """Run a slice of the player in node and return what ``call`` prints."""
    node = shutil.which("node") or ""
    if not node:
        pytest.skip("node is not installed")
    src = _player()
    body = src[src.index(fn_start) : src.index(fn_end)]
    result = subprocess.run(  # noqa: S603
        [node, "-e", prelude + "\n" + body + "\n" + call],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout.strip()


def test_glyph_text_names_the_module_not_two_initials() -> None:
    labels = [
        "NCD - Screenings",
        "NCD",
        "HIV",
        "TB",
        "Health Equity - Simple Measures",
        "Malaria",
        "PHEM",
        "Nutrition",
        "",
    ]
    out = _run_player_fn(
        "  var MODULE_CODES",
        "  var clipped",
        f"console.log(JSON.stringify({json.dumps(labels)}.map(glyphText)))",
    )

    assert json.loads(out) == [
        "NCD",
        "NCD",
        "HIV",
        "TB",
        "HE",
        "MAL",
        "PHEM",
        "NUT",
        "TV",
    ]


def test_year_from_cards_prefers_efy_then_the_most_common_year() -> None:
    prelude = (
        "var TITLES = [];"
        "function isVisible() { return true; }"
        "var document = { querySelectorAll: function () {"
        " return TITLES.map(function (t) { return { textContent: t }; }); } };"
    )
    cases = [
        ["Cases 2018", "Deaths 2018", "Coverage 2017"],
        ["Cases 2017 EFY/ 2024", "Deaths 2024", "Trend 2024"],
        ["Trend by month", "Per 1000 population"],
    ]
    out = _run_player_fn(
        "  var CARD_TITLE_SELECTOR",
        "  function paintChrome",
        f"console.log(JSON.stringify({json.dumps(cases)}.map(function (c) {{"
        " TITLES = c; return yearFromCards(); })));",
        prelude,
    )

    assert json.loads(out) == ["2018 EFY", "2017 EFY", ""]
