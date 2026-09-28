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
"""The PHC page can be framed by the dashboard PHC tab without its header."""

from __future__ import annotations

import pytest
from flask import Flask

from superset import hpc

PHC_URL = "https://public.tableau.com/views/PHCDashboard2026/EthiopiaPHCDashboard2026"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(hpc, "_require_login", lambda: None)
    app = Flask(__name__, template_folder="../../superset/templates")
    app.config["PHC_MONITORING_DASHBOARD_IFRAME_URL"] = PHC_URL
    app.register_blueprint(hpc.hpc_bp)
    return app.test_client()


def test_standalone_page_keeps_its_header(client) -> None:
    body = client.get("/hpc/").get_data(as_text=True)

    assert 'class="topbar"' in body
    assert "Back to portal" in body
    assert f'src="{PHC_URL}"' in body


def test_embedded_page_drops_the_header_and_fills_the_frame(client) -> None:
    body = client.get("/hpc/?embedded=1").get_data(as_text=True)

    assert 'class="topbar"' not in body
    assert '<body class="embedded">' in body
    assert f'src="{PHC_URL}"' in body


def test_only_the_portal_may_frame_the_page(client) -> None:
    response = client.get("/hpc/?embedded=1")
    csp = response.headers["Content-Security-Policy"]

    assert "frame-ancestors 'self'" in csp
    assert "frame-src 'self' https://public.tableau.com" in csp
    assert "X-Frame-Options" not in response.headers
