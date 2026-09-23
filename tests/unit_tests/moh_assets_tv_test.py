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

from superset.moh_assets import (
    _render_tv_page,
    _tv_page_payload,
    default_tv_theme,
)
from superset.utils import json

SLIDES = {
    "dashboard": "/superset/dashboard/8/?standalone=2",
    "slides": [{"path": ["Services Delivery", "NCD"], "label": "NCD"}],
}


def test_default_tv_theme_uses_the_type_tokens() -> None:
    theme = default_tv_theme({"tv_size_floor": 22, "tv_size_chart": 24})

    assert theme["token"] == {"fontSize": 22}
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
    assert payload["slides"] == [{"path": ["Services Delivery", "NCD"], "label": "NCD"}]


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
