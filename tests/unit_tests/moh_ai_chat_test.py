# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from superset.moh_ai_chat import _build_ai_chat_url


def test_build_ai_chat_url_includes_signed_token(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret")
    monkeypatch.setenv("AUTH_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("AUTH_JWT_EXPIRE_MINUTES", "60")
    monkeypatch.setenv("AUTH_ADMIN_EMAILS", "admin@example.com")

    user = SimpleNamespace(email="admin@example.com", username="alice")
    url = _build_ai_chat_url("https://example.com/chat?foo=bar", user)

    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert params["foo"] == ["bar"]
    assert "token" in params
    assert params["token"][0]


def test_build_ai_chat_url_leaves_url_unchanged_without_secret(monkeypatch) -> None:
    monkeypatch.delenv("AUTH_JWT_SECRET", raising=False)
    monkeypatch.delenv("AUTH_JWT_ALGORITHM", raising=False)
    monkeypatch.delenv("AUTH_JWT_EXPIRE_MINUTES", raising=False)
    monkeypatch.delenv("AUTH_ADMIN_EMAILS", raising=False)

    user = SimpleNamespace(email="user@example.com", username="bob")
    url = _build_ai_chat_url("https://example.com/chat", user)

    assert url == "https://example.com/chat"
