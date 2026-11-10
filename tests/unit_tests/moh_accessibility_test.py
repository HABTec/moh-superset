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
from pathlib import Path
from typing import Any

import jinja2

import superset

TEMPLATES = Path(superset.__file__).parent / "templates"


class _Macros:
    def get_nonce(self) -> str:
        return ""


class _SecurityManager:
    def __init__(self, is_admin: bool) -> None:
        self._is_admin = is_admin

    def is_admin(self) -> bool:
        return self._is_admin


class _AppBuilder:
    def __init__(self, is_admin: bool) -> None:
        self.sm = _SecurityManager(is_admin)


class _User:
    is_authenticated = True
    first_name = "Reader"
    username = "reader"


def _render(name: str, is_admin: bool = False) -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES)),
        autoescape=jinja2.select_autoescape(["html"]),
    )
    context: dict[str, Any] = {
        "current_user": _User(),
        "appbuilder": _AppBuilder(is_admin),
        "config": {"THEME_DARK": True},
        "macros": _Macros(),
    }
    return env.get_template(name).render(**context)


def test_head_template_defines_high_contrast_api_and_styles() -> None:
    html = _render("moh_accessibility_head.html")

    assert "window.mohAccessibility" in html
    assert "prefers-contrast: more" in html
    assert 'html[data-moh-contrast="high"]' in html
    # Dark mode combines with high contrast instead of being replaced by it.
    assert 'html[data-moh-contrast="high"][data-theme-mode="dark"]' in html
    assert ":focus-visible" in html


def test_head_custom_extra_includes_accessibility_head() -> None:
    source = (TEMPLATES / "head_custom_extra.html").read_text()

    assert '{% include "moh_accessibility_head.html" %}' in source


def test_portal_bar_shows_accessibility_menu_to_readers() -> None:
    html = _render("tail_js_custom_extra.html", is_admin=False)

    assert 'id="mohPortalA11yToggle"' in html
    assert 'id="mohPortalHighContrast"' in html
    assert "High contrast" in html
    assert 'aria-expanded="false"' in html


def test_admins_keep_superset_navbar_without_portal_menu() -> None:
    html = _render("tail_js_custom_extra.html", is_admin=True)

    assert "mohPortalA11yToggle" not in html
