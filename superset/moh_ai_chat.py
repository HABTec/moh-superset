# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.
"""
MoH AI Assistant — Gemini-powered chat backed by the Superset MCP server.

Wires a single page at /ai-chat/ where logged-in admins can chat with
Gemini. The handler running here holds the GEMINI_API_KEY and opens an
MCP session against the Superset MCP server, so:

  - the API key never leaves the Flask container,
  - every tool call (list_dashboards, execute_sql, ...) is RBAC-checked
    by the MCP server as the configured user,
  - audit trail lands in Superset's action log automatically.

Flow:
    Browser ──POST /ai-chat/api/message──> Flask handler
                                              │
                                              ├─► Gemini API
                                              │
                                              └─► MCP server (RBAC)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user

from superset.superset_typing import FlaskResponse

logger = logging.getLogger(__name__)

# Single blueprint exposing /ai-chat/ (HTML page) and
# /ai-chat/api/message (JSON POST endpoint). Registered with the Flask
# app via the BLUEPRINTS list in superset/moh_branding.py — no edits to
# upstream Superset init code required.
ai_chat_bp = Blueprint(
    "moh_ai_chat",
    __name__,
    template_folder="templates",
)


# ---------------------------------------------------------------------------
# Configuration helpers — all driven by environment variables so a single
# code path works in Docker, native Ubuntu, and local dev.
# ---------------------------------------------------------------------------

def _mcp_url() -> str:
    """Where this Flask process reaches the MCP server.

    Default points at the Docker compose service name `superset-mcp`,
    which is how containers find each other on the compose network. For
    a native (non-Docker) install, set MCP_INTERNAL_URL=http://localhost:5008/mcp
    in the Flask environment.
    """
    return os.environ.get("MCP_INTERNAL_URL", "http://superset-mcp:5008/mcp")


def _gemini_api_key() -> str | None:
    """First configured key (used for the 'configured?' check on the page)."""
    keys = _gemini_api_keys()
    return keys[0] if keys else None


def _gemini_api_keys() -> list[str]:
    """All Gemini API keys, in priority order.

    Reads `GEMINI_API_KEY` (the primary) plus indexed extras `GEMINI_API_KEY_2`,
    `GEMINI_API_KEY_3`, ... The runtime tries them in order; if a request fails
    with a per-key rate-limit / quota error, it retries with the next key.
    Returns [] if nothing is configured.
    """
    keys: list[str] = []
    primary = os.environ.get("GEMINI_API_KEY")
    if primary:
        keys.append(primary)
    i = 2
    while True:
        k = os.environ.get(f"GEMINI_API_KEY_{i}")
        if not k:
            break
        keys.append(k)
        i += 1
    return keys


def _is_per_key_quota_error(exc: BaseException) -> bool:
    """True if the failure is a per-key rate-limit / quota error.

    Walks the exception chain (asyncio TaskGroup wraps the real cause in an
    ExceptionGroup) so we catch the upstream message even when buried.
    Specifically excludes 503 / overloaded — those are model-wide and rotating
    keys won't help.
    """
    msgs: list[str] = []

    def _collect(e: BaseException) -> None:
        msgs.append(str(e))
        for sub in getattr(e, "exceptions", None) or ():
            _collect(sub)
        for chained in (e.__cause__, e.__context__):
            if chained is not None:
                msgs.append(str(chained))

    _collect(exc)
    joined = " || ".join(msgs).lower()
    if "503" in joined or "unavailable" in joined or "overloaded" in joined or "high demand" in joined:
        return False
    return "429" in joined or "rate" in joined or "quota" in joined or "resource_exhausted" in joined


def _gemini_model() -> str:
    # Free tier on AI Studio gives generous quota for 2.5-flash.
    # Override via env if you want to spend money on 2.5-pro.
    return os.environ.get("MOH_AI_MODEL", "gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Provider selection — pick between Gemini and Claude with a single env var.
# ---------------------------------------------------------------------------

def _ai_provider() -> str:
    """Which LLM provider to use: 'gemini' (default) or 'claude'."""
    return (os.environ.get("MOH_AI_PROVIDER") or "gemini").lower()


def _claude_api_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY")


def _claude_model() -> str:
    # Sonnet 4.6 is the right default for tool-heavy chart workflows: very
    # strong at chained tool calls, fast, and much cheaper than Opus.
    return os.environ.get("MOH_CLAUDE_MODEL", "claude-sonnet-4-6")


def _openai_api_key() -> str | None:
    return os.environ.get("OPENAI_API_KEY")


def _openai_model() -> str:
    # gpt-4o-mini is the right default: cheap, fast, solid tool-call support.
    # Override with MOH_OPENAI_MODEL=gpt-4o (or gpt-4.1 etc.) for harder reasoning.
    return os.environ.get("MOH_OPENAI_MODEL", "gpt-4o-mini")


def _provider_configured() -> bool:
    """True if the active provider has at least one API key."""
    p = _ai_provider()
    if p == "claude":
        return bool(_claude_api_key())
    if p == "openai":
        return bool(_openai_api_key())
    return bool(_gemini_api_key())


def _provider_display_label() -> str:
    """Short human-readable label for the active provider, used in the page header."""
    p = _ai_provider()
    if p == "claude":
        return _claude_model()
    if p == "openai":
        return _openai_model()
    return _gemini_model()


# ---------------------------------------------------------------------------
# Authorization — admin-only. The MCP tools include `execute_sql`, so we
# don't want to expose this surface to anyone other than admins for v1.
# ---------------------------------------------------------------------------

def _require_admin() -> tuple[Any, int] | None:
    """Return a Flask response tuple if the caller isn't an admin, else None."""
    from superset import security_manager  # local import: avoids circularity at import time

    if not getattr(current_user, "is_authenticated", False):
        return jsonify({"error": "unauthorized"}), 401
    if not security_manager.is_admin():
        return jsonify({"error": "admin only"}), 403
    return None


# ---------------------------------------------------------------------------
# Core: ask Gemini a question with the MCP server attached as a tool source.
# ---------------------------------------------------------------------------

def _patch_genai_for_bool_schemas() -> None:
    """Work around a google-genai bug.

    `_mcp_utils._filter_to_supported_schema` recurses into every JSON-Schema
    field unconditionally, but JSON Schema allows boolean values for
    `additionalProperties`, `items`, etc. The Superset MCP tool schemas
    legitimately contain `additionalProperties: false`, and the SDK then
    blows up with `'bool' object has no attribute 'items'`.

    We replace the function with a copy that recurses through dicts and
    lists but returns scalars (bool/str/int/None) unchanged. Idempotent.
    """
    try:
        from google.genai import _mcp_utils  # type: ignore[attr-defined]
        from google.genai import types as _types
    except ImportError:
        return
    if getattr(_mcp_utils, "_moh_filter_patched", False):
        return

    schema_field_names = ("items", "additionalProperties", "additional_properties")
    list_schema_field_names = ("anyOf", "any_of", "oneOf", "one_of")
    dict_schema_field_names = ("properties", "defs", "$defs")
    extra_supported = {"additionalProperties", "anyOf", "oneOf", "$defs", "$ref"}

    def _filter(schema):  # type: ignore[no-untyped-def]
        # Scalars (bool, None, str, int) and lists pass through untouched.
        if not isinstance(schema, dict):
            return schema

        supported = set(_types.JSONSchema.model_fields.keys()) | extra_supported
        out: dict = {}
        for field_name, field_value in schema.items():
            if field_name in schema_field_names:
                out[field_name] = _filter(field_value)
            elif field_name in list_schema_field_names:
                if isinstance(field_value, list):
                    out[field_name] = [_filter(v) for v in field_value]
                else:
                    out[field_name] = _filter(field_value)
            elif field_name in dict_schema_field_names:
                if isinstance(field_value, dict):
                    out[field_name] = {k: _filter(v) for k, v in field_value.items()}
                else:
                    out[field_name] = field_value
            elif field_name in supported:
                out[field_name] = field_value
        return out

    _mcp_utils._filter_to_supported_schema = _filter
    _mcp_utils._moh_filter_patched = True
    logger.info("Patched google.genai._mcp_utils._filter_to_supported_schema")


async def _ask_claude(prompt: str, history: list[dict]) -> str:
    """Send `prompt` to Claude with the MCP tools wired in.

    Anthropic's hosted-MCP feature requires a publicly reachable MCP URL,
    which our localhost MCP server isn't. So we use the standard pattern:
    open the MCP session client-side, list its tools, expose them to Claude
    via Anthropic's native ``tools=[...]`` parameter, and run the agent loop
    locally — every time Claude wants to call a tool, we forward through MCP
    and feed the result back into the next message.
    """
    from anthropic import AsyncAnthropic
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    api_key = _claude_api_key()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to docker/.env-local "
            "and recreate the superset container."
        )

    client = AsyncAnthropic(api_key=api_key)

    # Anthropic's message format: alternating user/assistant turns. History
    # uses Gemini's "model"/"user" naming, so map that.
    messages: list[dict] = []
    for turn in history:
        role = turn.get("role")
        text = turn.get("content") or ""
        if not text:
            continue
        if role == "user":
            messages.append({"role": "user", "content": text})
        elif role in ("model", "assistant"):
            messages.append({"role": "assistant", "content": text})
    messages.append({"role": "user", "content": prompt})

    async with streamablehttp_client(_mcp_url()) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            anthropic_tools = [
                {
                    "name": t.name,
                    "description": (t.description or "")[:1024],
                    "input_schema": t.inputSchema or {"type": "object", "properties": {}},
                }
                for t in tools_result.tools
            ]

            model = _claude_model()
            # Cap the agent loop the same way we cap Gemini — prevents a runaway
            # tool chain from burning credits.
            for _iteration in range(12):
                response = await client.messages.create(
                    model=model,
                    max_tokens=4096,
                    tools=anthropic_tools,
                    messages=messages,
                )

                if response.stop_reason != "tool_use":
                    # Final answer — collect any text blocks.
                    texts = [
                        b.text for b in response.content
                        if getattr(b, "type", None) == "text"
                    ]
                    return "\n".join(t for t in texts if t).strip() or "(empty response)"

                # Tool-use turn: record assistant message verbatim, then run
                # each tool call against MCP and append the results.
                messages.append({"role": "assistant", "content": response.content})
                tool_results: list[dict] = []
                for block in response.content:
                    if getattr(block, "type", None) != "tool_use":
                        continue
                    try:
                        result = await session.call_tool(block.name, block.input or {})
                        out_text = "\n".join(
                            getattr(c, "text", "") for c in (result.content or [])
                            if getattr(c, "text", None)
                        ) or "(tool returned no text content)"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": out_text,
                        })
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("MCP tool '%s' failed: %s", block.name, exc)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Tool error: {exc}",
                            "is_error": True,
                        })
                messages.append({"role": "user", "content": tool_results})

            return "(hit the 12-iteration tool-call cap before Claude produced a final answer)"


async def _ask_openai(prompt: str, history: list[dict]) -> str:
    """Send `prompt` to OpenAI with the MCP tools wired in.

    OpenAI's hosted-MCP feature in the Responses API requires a publicly
    reachable MCP URL — our localhost MCP isn't. So we use the chat-completions
    pattern: open the MCP session client-side, list its tools, expose them to
    OpenAI as native ``tools=[{"type": "function", ...}]``, and run the agent
    loop locally — every time OpenAI returns ``tool_calls``, we forward through
    MCP and feed the results back as ``role="tool"`` messages.
    """
    import json as _json

    from openai import AsyncOpenAI
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    api_key = _openai_api_key()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to docker/.env-local "
            "and recreate the superset container."
        )

    client = AsyncOpenAI(api_key=api_key)

    # OpenAI's chat-completions format: list of role-tagged messages.
    # History uses Gemini's "model"/"user" convention, which we map.
    messages: list[dict] = []
    for turn in history:
        role = turn.get("role")
        text = turn.get("content") or ""
        if not text:
            continue
        if role == "user":
            messages.append({"role": "user", "content": text})
        elif role in ("model", "assistant"):
            messages.append({"role": "assistant", "content": text})
    messages.append({"role": "user", "content": prompt})

    async with streamablehttp_client(_mcp_url()) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": (t.description or "")[:1024],
                        "parameters": t.inputSchema or {"type": "object", "properties": {}},
                    },
                }
                for t in tools_result.tools
            ]

            model = _openai_model()
            for _iteration in range(12):
                response = await client.chat.completions.create(
                    model=model,
                    tools=openai_tools,
                    messages=messages,
                )
                msg = response.choices[0].message

                if not msg.tool_calls:
                    return (msg.content or "").strip() or "(empty response)"

                # Tool-use turn: append the assistant message verbatim so the
                # API sees the same tool_calls we're about to respond to.
                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    try:
                        args = _json.loads(tc.function.arguments) if tc.function.arguments else {}
                        result = await session.call_tool(tc.function.name, args)
                        out_text = "\n".join(
                            getattr(c, "text", "") for c in (result.content or [])
                            if getattr(c, "text", None)
                        ) or "(tool returned no text content)"
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("MCP tool '%s' failed: %s", tc.function.name, exc)
                        out_text = f"Tool error: {exc}"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": out_text,
                    })

            return "(hit the 12-iteration tool-call cap before OpenAI produced a final answer)"


def _extract_text(response) -> str:  # type: ignore[no-untyped-def]
    """Pull a usable string out of a Gemini response, even when ``response.text`` is empty.

    Empty `.text` happens in two common cases:
    1. The model finished with a function-call part only (no text part) — usually
       when ``automatic_function_calling.maximum_remote_calls`` is hit mid-loop.
    2. Safety filters blocked the response (`finish_reason = SAFETY` etc.)

    We walk every candidate's parts to find any text the SDK skipped, and if
    there's still nothing we return a *diagnostic* message instead of a
    confusing "(empty response)" so the user can see what actually happened.
    """
    text = (getattr(response, "text", None) or "").strip()
    if text:
        return text

    parts_text: list[str] = []
    finish_reasons: list[str] = []
    attempted_tools: list[str] = []
    for cand in getattr(response, "candidates", None) or []:
        fr = getattr(cand, "finish_reason", None)
        if fr is not None:
            finish_reasons.append(str(fr))
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", None) or []:
            ptxt = getattr(part, "text", None)
            if ptxt:
                parts_text.append(ptxt)
            fc = getattr(part, "function_call", None)
            if fc is not None:
                fname = getattr(fc, "name", None)
                if fname:
                    attempted_tools.append(fname)

    joined = "\n".join(p for p in parts_text if p).strip()
    if joined:
        return joined

    logger.warning(
        "Gemini returned no text. finish_reasons=%s attempted_tools=%s",
        finish_reasons, attempted_tools,
    )
    if any("MAX_TOKENS" in fr.upper() for fr in finish_reasons):
        return ("(model ran out of output tokens before answering — "
                "try a shorter prompt or set MOH_AI_MODEL=gemini-2.5-pro)")
    if any("SAFETY" in fr.upper() or "RECITATION" in fr.upper() for fr in finish_reasons):
        return f"(response blocked by Gemini safety filter; finish_reason={finish_reasons})"
    if any("MALFORMED" in fr.upper() for fr in finish_reasons):
        tool_hint = f" while calling '{attempted_tools[-1]}'" if attempted_tools else ""
        return (
            f"(Gemini Flash produced a malformed function call{tool_hint}. "
            "This is a known Flash weakness with complex tool schemas. "
            "Workarounds: (1) ask for an 'explore link' instead of a 'chart' — "
            "`generate_explore_link` has a simpler schema than `generate_chart`. "
            "(2) Set MOH_AI_MODEL=gemini-2.5-pro in docker/.env-local for stricter "
            "schema handling. (3) Retry — sometimes the next attempt succeeds.)"
        )
    return ("(model finished with tool calls only — likely hit the 12-call agent loop cap. "
            "Try a more specific prompt with fewer required steps.)")


async def _ask_gemini(prompt: str, history: list[dict]) -> str:
    """Send `prompt` to Gemini; let it use MCP tools as needed; return text."""
    # Lazy imports so the rest of Superset still boots if these aren't installed.
    from google import genai
    from google.genai import types
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    _patch_genai_for_bool_schemas()

    keys = _gemini_api_keys()
    if not keys:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to docker/.env-local "
            "(or your shell env for native installs) and restart the superset container."
        )

    # Re-hydrate prior turns into Gemini's content-list format. We keep
    # history in the browser (not on the server) so the page is stateless;
    # this trades a slightly bigger request payload for zero new DB tables.
    contents: list[types.Content] = []
    for turn in history:
        role = turn.get("role")
        text = turn.get("content") or ""
        if role not in ("user", "model") or not text:
            continue
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))

    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))

    # Open the MCP transport once and reuse it across key-rotation retries.
    # The Gemini SDK auto-discovers tools (tools/list), forwards tool calls
    # (tools/call), and loops until the model stops or hits maximum_remote_calls.
    async with streamablehttp_client(_mcp_url()) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            last_exc: Exception | None = None
            for idx, api_key in enumerate(keys):
                client = genai.Client(api_key=api_key)
                try:
                    response = await client.aio.models.generate_content(
                        model=_gemini_model(),
                        contents=contents,
                        config=types.GenerateContentConfig(
                            temperature=0,
                            tools=[session],
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                                maximum_remote_calls=12,
                            ),
                        ),
                    )
                    if idx > 0:
                        logger.info("AI chat succeeded on backup key #%d", idx + 1)
                    return _extract_text(response)
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if _is_per_key_quota_error(exc) and idx + 1 < len(keys):
                        logger.warning(
                            "Gemini key #%d hit per-key rate/quota limit; "
                            "rotating to key #%d (%d total configured)",
                            idx + 1, idx + 2, len(keys),
                        )
                        continue
                    raise

            assert last_exc is not None  # loop must have raised or returned
            raise last_exc


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@ai_chat_bp.route("/ai-chat/")
def ai_chat_page() -> FlaskResponse:
    """Serve the chat UI (HTML page)."""
    if (denied := _require_admin()) is not None:
        return denied
    return render_template(
        "superset/ai_chat.html",
        # Backwards-compatible name: the template still calls this gemini_model,
        # but it now shows whichever model is active (Gemini *or* Claude).
        gemini_model=_provider_display_label(),
        gemini_configured=_provider_configured(),
        ai_provider=_ai_provider(),
    )


@ai_chat_bp.route("/ai-chat/api/message", methods=["POST"])
def ai_chat_message() -> FlaskResponse:
    """Handle one user message; return Gemini's answer as JSON."""
    if (denied := _require_admin()) is not None:
        return denied

    payload = request.get_json(silent=True) or {}
    user_message = (payload.get("message") or "").strip()
    history = payload.get("history") or []
    if not user_message:
        return jsonify({"error": "empty message"}), 400

    provider = _ai_provider()
    if provider == "claude":
        asker = _ask_claude
    elif provider == "openai":
        asker = _ask_openai
    else:
        asker = _ask_gemini

    try:
        text = asyncio.run(asker(user_message, history))
    except RuntimeError as exc:
        # Configuration error — surface it to the UI so the admin can fix it.
        logger.warning("AI chat config error: %s", exc)
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:  # noqa: BLE001
        # asyncio TaskGroup wraps the real error in an ExceptionGroup; walk the
        # tree so we can match on the actual upstream message.
        all_msgs: list[str] = []

        def _collect(e: BaseException) -> None:
            all_msgs.append(str(e))
            inner = getattr(e, "exceptions", None)
            if inner:
                for sub in inner:
                    _collect(sub)
            cause = e.__cause__ or e.__context__
            if cause is not None:
                all_msgs.append(str(cause))

        _collect(exc)
        joined = " || ".join(all_msgs)
        lower = joined.lower()

        # Provider-aware error message wording.
        provider_name = {"claude": "Claude", "openai": "OpenAI"}.get(provider, "Gemini")
        rate_hint = {
            "gemini": "Free tier is ~10 requests/min per key — wait ~60 seconds, add a fallback "
                      "GEMINI_API_KEY_2, or set MOH_AI_MODEL to a different model.",
            "claude": "Check your Anthropic usage tier — you may be hitting per-minute or daily caps.",
            "openai": "Check your OpenAI tier and billing — new accounts start at Tier 0 with "
                      "very tight RPM. Add a payment method and prepay $5-10 to unlock normal limits "
                      "(see https://platform.openai.com/settings/organization/billing).",
        }.get(provider, "Wait ~60 seconds and try again.")

        if "429" in joined or "rate" in lower or "quota" in lower or "resource_exhausted" in lower:
            logger.info("%s rate-limited: %s", provider_name, joined[:400])
            return jsonify({
                "error": f"{provider_name} rate limit hit. {rate_hint}"
            }), 429
        if "503" in joined or "unavailable" in lower or "overloaded" in lower or "high demand" in lower:
            logger.info("%s service unavailable: %s", provider_name, joined[:400])
            return jsonify({
                "error": f"{provider_name} is overloaded (transient upstream issue). "
                         "Try again in a few seconds."
            }), 503
        logger.exception("AI chat request failed")
        return jsonify({"error": "AI request failed (see server logs)"}), 500

    return jsonify({"reply": text})
