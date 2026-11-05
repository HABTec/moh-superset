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
from pathlib import Path
from typing import Any

import pytest
from werkzeug.exceptions import NotFound

from superset.moh_assets import _GUIDE_DIR, user_guide, user_guide_asset


def _sign_in(monkeypatch: pytest.MonkeyPatch, signed_in: bool = True) -> None:
    monkeypatch.setattr(
        "superset.moh_assets.current_user",
        type("User", (), {"is_authenticated": signed_in}),
    )


def test_guide_sends_anonymous_users_to_login(
    app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sign_in(monkeypatch, signed_in=False)

    with app.test_request_context("/guide/"):
        response = user_guide()

    assert response.status_code == 302
    assert response.location == "/login/?next=/guide/"


def test_guide_files_send_anonymous_users_to_login(
    app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sign_in(monkeypatch, signed_in=False)
    path = "/guide/images/guide/login.png"

    with app.test_request_context(path):
        response = user_guide_asset("images/guide/login.png")

    assert response.status_code == 302
    assert response.location == f"/login/?next={path}"


def test_guide_page_is_served_same_origin_only(
    app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sign_in(monkeypatch)

    with app.test_request_context("/guide/"):
        response = user_guide()
        response.direct_passthrough = False

    csp = response.headers["Content-Security-Policy"]
    assert response.status_code == 200
    assert "script-src 'self'" in csp
    assert "https:" not in csp
    assert response.headers["Cache-Control"] == "no-cache"
    assert "User Guide" in response.get_data(as_text=True)


def test_guide_refuses_paths_outside_its_folder(
    app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sign_in(monkeypatch)

    with app.test_request_context("/guide/x"):
        with pytest.raises(NotFound):
            user_guide_asset("../user_guide.html")


def test_built_guide_contains_every_file_its_page_names() -> None:
    guide = Path(_GUIDE_DIR)
    html = (guide / "index.html").read_text()
    names = re.findall(r'(?:src|href)="/guide/([^"]+)"', html)

    assert any(name.startswith("assets/") for name in names)
    for name in names:
        assert (guide / name).is_file(), name
