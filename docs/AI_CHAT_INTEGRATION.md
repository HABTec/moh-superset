# AI Assistant Page — Integration Guide

This document explains how the **AI Assistant** page at `/ai-chat/` is wired
into Superset. It covers what each file does, what each non-trivial line
does, and how the pieces talk to each other at runtime.

> Audience: a developer who knows Python and Flask reasonably well but is
> seeing this codebase for the first time. If you only need "how do I run
> it?", jump to [Running it locally](#running-it-locally).

---

## TL;DR

| | |
|---|---|
| **URL** | `http://localhost:8088/ai-chat/` |
| **Who can access** | Logged-in users with the **Admin** role |
| **LLM** | Google Gemini (default `gemini-2.5-flash`, free tier) |
| **Tools** | Provided by the local Superset MCP server at `http://superset-mcp:5008/mcp` |
| **API key** | `GEMINI_API_KEY` in `docker/.env-local` (server-side only — never sent to the browser) |
| **History** | Lives in the browser tab; refreshing starts a new conversation |
| **Streaming** | No — v1 returns the full reply in one response |

---

## Architecture

```text
┌──────────────┐     POST /ai-chat/api/message        ┌────────────────────┐
│   Browser    │  ─────────────────────────────────►  │  Flask handler     │
│   (chat UI)  │  ◄─────────────────────────────────  │  (admin-only)      │
└──────────────┘     JSON {"reply": "..."}            │                    │
                                                       │  GEMINI_API_KEY    │
                                                       │  lives here        │
                                                       └────┬───────────┬───┘
                                                            │           │
                                       Gemini API           │           │  MCP JSON-RPC
                                       (HTTPS to Google)    │           │  over Streamable HTTP
                                                            │           │
                                                            ▼           ▼
                                                     ┌────────────┐  ┌─────────────────┐
                                                     │   Gemini   │  │  superset-mcp   │
                                                     │   2.5      │  │  (RBAC + audit) │
                                                     │   Flash    │  │  :5008/mcp      │
                                                     └────────────┘  └────────┬────────┘
                                                                              │
                                                                              ▼
                                                                    ┌──────────────────┐
                                                                    │ Postgres / Redis │
                                                                    │ (Superset data)  │
                                                                    └──────────────────┘
```

Three things to notice:

1. **The API key is server-side.** The browser only ever sends user text; the
   Flask handler injects the Gemini key when calling the LLM.
2. **MCP is the only tool surface.** Every action the model takes (listing
   dashboards, running SQL, etc.) goes through the MCP server, which does
   its own RBAC checks and writes to Superset's action log. Nothing
   bypasses Superset's permission model.
3. **The LLM never sees the database directly.** It only sees MCP tool
   responses, which are scoped, paginated, and size-guarded by the MCP
   middleware stack (see `superset/mcp_service/middleware.py`).

---

## Files added

| File | Type | Purpose |
|---|---|---|
| [`superset/moh_ai_chat.py`](../superset/moh_ai_chat.py) | new | Flask blueprint: page route + JSON API route |
| [`superset/templates/superset/ai_chat.html`](../superset/templates/superset/ai_chat.html) | new | Chat UI (vanilla HTML/CSS/JS) |
| [`docker/requirements-local.txt`](../docker/requirements-local.txt) | new | Adds `google-genai` to every container start |
| [`docker/.env-local`](../docker/.env-local) | new (gitignored) | Holds `GEMINI_API_KEY` |
| [`docs/AI_CHAT_INTEGRATION.md`](./AI_CHAT_INTEGRATION.md) | new | This document |

## Files modified

| File | Change |
|---|---|
| [`superset/moh_branding.py`](../superset/moh_branding.py) | Imports `ai_chat_bp` and exports it via `BLUEPRINTS = [_ai_chat_bp]` so Superset auto-registers it |
| [`superset/templates/superset/landing.html`](../superset/templates/superset/landing.html) | Adds an `AI Assistant` link to the homepage nav |

No upstream Superset files (`superset/initialization/`, `superset/config.py`,
etc.) were touched. Everything sits in MoH-prefixed modules so future
upstream merges don't conflict.

---

## How the registration works

Superset's `superset/initialization/__init__.py` already iterates
`config["BLUEPRINTS"]` and registers each one with the Flask app:

```python
def register_blueprints(self) -> None:
    for bp in self.config["BLUEPRINTS"]:
        try:
            logger.info("Registering blueprint: %s", bp.name)
            self.superset_app.register_blueprint(bp)
        except Exception:
            logger.exception("blueprint registration failed")
```

We populate that list in [`superset/moh_branding.py`](../superset/moh_branding.py):

```python
from superset.moh_ai_chat import ai_chat_bp as _ai_chat_bp
BLUEPRINTS = [_ai_chat_bp]
```

Because `superset_config_docker.py` does `from superset.moh_branding import *`,
that `BLUEPRINTS` symbol propagates into Flask config at startup, and the
blueprint is mounted automatically. This is the **only** integration point
with upstream Superset.

---

## `superset/moh_ai_chat.py` — annotated walkthrough

### Imports

```python
import asyncio       # we run async MCP code from a sync Flask handler
import logging       # standard server-side logger
import os            # read env vars (API key, model, MCP URL)
from typing import Any

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user

from superset.superset_typing import FlaskResponse
```

- `asyncio.run(...)` lets the blueprint stay synchronous (Superset's WSGI
  app is sync) while still using the async MCP and Gemini SDK APIs.
- `current_user` is Flask-Login's proxy for the authenticated user — set
  by Superset's existing auth middleware before our handler runs.
- `FlaskResponse` is Superset's typing alias used everywhere; we follow
  the same convention for consistency.

### Blueprint declaration

```python
ai_chat_bp = Blueprint(
    "moh_ai_chat",
    __name__,
    template_folder="templates",
)
```

- `"moh_ai_chat"` is the unique blueprint name shown in startup logs.
- `template_folder="templates"` means Jinja resolves
  `render_template("superset/ai_chat.html")` against
  `superset/templates/superset/ai_chat.html`.

### Configuration helpers

```python
def _mcp_url() -> str:
    return os.environ.get("MCP_INTERNAL_URL", "http://superset-mcp:5008/mcp")
```

The default points at the **docker compose service name** (`superset-mcp`),
which is how containers find each other on the compose network. For a
native (non-Docker) install, set `MCP_INTERNAL_URL=http://localhost:5008/mcp`
in the Flask environment.

```python
def _gemini_api_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY")

def _gemini_model() -> str:
    return os.environ.get("MOH_AI_MODEL", "gemini-2.5-flash")
```

Both come from env. Storing the API key in env (loaded from `docker/.env-local`)
keeps it out of source control and out of the browser.

### Authorization

```python
def _require_admin() -> tuple[Any, int] | None:
    from superset import security_manager
    if not getattr(current_user, "is_authenticated", False):
        return jsonify({"error": "unauthorized"}), 401
    if not security_manager.is_admin():
        return jsonify({"error": "admin only"}), 403
    return None
```

Why this shape rather than the FAB `@has_access` decorator?

- `@has_access` requires the route to be a method on a `BaseView`/`ModelView`
  subclass with permissions registered. Plain Flask blueprints don't have
  that — and we want a plain blueprint because it's simpler and doesn't
  introduce a fake "view" just to satisfy the decorator.
- This helper returns a **response tuple if denied, `None` if allowed**, so
  callers can do `if (denied := _require_admin()) is not None: return denied`.
- The `from superset import security_manager` is intentionally inside the
  function — importing at module load time creates a circular import in
  some Superset boot orderings.

### Calling Gemini with MCP attached

This is the heart of the file. Annotated:

```python
async def _ask_gemini(prompt: str, history: list[dict]) -> str:
    from google import genai
    from google.genai import types
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
```

Imports are inside the function so Superset still boots if these packages
fail to install — the blueprint fails *only* at request time with a clear
error, instead of crashing the whole app.

```python
    api_key = _gemini_api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. ...")
```

Fail fast with a human-readable message; the route handler catches this
and renders it in the chat as an error bubble.

```python
    client = genai.Client(api_key=api_key)
```

`google-genai` SDK client. Stateless — fine to construct per request.

```python
    contents: list[types.Content] = []
    for turn in history:
        role = turn.get("role")
        text = turn.get("content") or ""
        if role not in ("user", "model") or not text:
            continue
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))

    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))
```

We rebuild the conversation from the browser-supplied history each turn.
This trades a slightly larger request payload for **zero new database
tables**: there's nothing to migrate, nothing to clean up, and refreshing
the page = starting over.

The `if role not in ("user", "model")` guard rejects malformed history
sent by a tampered client. `parts=[Part.from_text(...)]` is the SDK's
required nesting structure; we only carry plain text turns (no inline
images, no tool calls — Gemini handles tool calls itself).

```python
    async with streamablehttp_client(_mcp_url()) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
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
    return response.text or "(empty response)"
```

This is the full integration in 12 lines:

1. `streamablehttp_client(url)` opens an HTTP+SSE transport to the MCP
   server. It's a context manager, so the connection is cleanly closed
   when the request finishes.
2. `ClientSession(read, write)` wraps the transport in the JSON-RPC
   protocol layer.
3. `await session.initialize()` performs the MCP handshake and capability
   exchange.
4. `client.aio.models.generate_content(..., tools=[session])` is the magic
   line. The Gemini SDK natively understands an MCP `ClientSession` as a
   tool source — it'll auto-discover tools (calls `tools/list`), forward
   any tool calls the model makes back through the session
   (`tools/call`), feed responses back into the conversation, and loop
   until the model stops calling tools or hits the `maximum_remote_calls`
   cap.
5. `temperature=0` makes responses deterministic per turn — useful when
   you're inspecting whether the model picked the right tool.
6. `maximum_remote_calls=12` caps the agentic loop. Without this, a
   pathological prompt could trigger a runaway tool-calling loop and
   drain free-tier quota.

A new MCP session is opened **per request**. That's intentional: it
keeps the code simple, avoids cross-request state, and the handshake is
cheap (~50 ms locally). If we hit a perf issue later we can add a
session pool — but premature optimization isn't worth it for an
admin-only page.

### Routes

```python
@ai_chat_bp.route("/ai-chat/")
def ai_chat_page() -> FlaskResponse:
    if (denied := _require_admin()) is not None:
        return denied
    return render_template(
        "superset/ai_chat.html",
        gemini_model=_gemini_model(),
        gemini_configured=bool(_gemini_api_key()),
    )
```

`gemini_configured` is forwarded to the template purely so we can render
a friendly setup-warning banner if the key is missing.

```python
@ai_chat_bp.route("/ai-chat/api/message", methods=["POST"])
def ai_chat_message() -> FlaskResponse:
    if (denied := _require_admin()) is not None:
        return denied

    payload = request.get_json(silent=True) or {}
    user_message = (payload.get("message") or "").strip()
    history = payload.get("history") or []
    if not user_message:
        return jsonify({"error": "empty message"}), 400

    try:
        text = asyncio.run(_ask_gemini(user_message, history))
    except RuntimeError as exc:
        logger.warning("AI chat config error: %s", exc)
        return jsonify({"error": str(exc)}), 500
    except Exception:  # noqa: BLE001
        logger.exception("AI chat request failed")
        return jsonify({"error": "AI request failed (see server logs)"}), 500

    return jsonify({"reply": text})
```

Two distinct error paths:

- `RuntimeError` → config error (e.g. missing API key). The actual
  message is forwarded to the UI because it's actionable for the admin.
- Anything else → log full traceback server-side, return a generic
  message client-side. Never leaks tracebacks or topology to the LLM /
  user.

`asyncio.run()` creates a fresh event loop per request, runs the async
function, and tears it down. We don't share a loop across requests
because Flask's WSGI workers are sync and we want each request fully
isolated.

---

## `ai_chat.html` — annotated walkthrough

The template is a single self-contained file: HTML, scoped CSS, vanilla
JS. No webpack build, no React, no external runtime deps. Same approach
as [`landing.html`](../superset/templates/superset/landing.html), and
the colors are reused so the page feels cohesive with the rest of the
MoH branding.

### Top of body

```html
<header class="topbar">
  <img class="logo-img" src="/static/assets/images/logomohnewww.png" ...>
  ...
  <nav class="appnav">
    <a href="/superset/welcome/">Home</a>
    <a href="/dashboard/list/">Dashboards</a>
    ...
    <a href="/ai-chat/" class="active">AI Assistant</a>
  </nav>
</header>
```

Mirrors the landing page's nav so the user has consistent top-nav links
on both pages.

### Hero / config warning

```html
<div class="hero">
  <h1>Ask about your data</h1>
  <p>Powered by <code>{{ gemini_model }}</code> via the Superset MCP server. Admin-only.</p>
</div>

{% if not gemini_configured %}
<div class="config-warn">
  <strong>Not configured:</strong> set <code>GEMINI_API_KEY</code> in
  <code>docker/.env-local</code> ...
</div>
{% endif %}
```

The `gemini_configured` Jinja flag is the only piece of dynamic content
in the template — it tells the admin exactly what to fix when the page
is broken.

### Example prompts

```html
<div class="examples">
  <button type="button" data-prompt="List my dashboards ...">List my dashboards</button>
  ...
</div>
```

Quick-fire seed prompts. The JS at the bottom binds clicks on these to
populate the textarea (and only the textarea — clicking does *not*
auto-send, so the user can edit before submitting).

### Messages container

```html
<div class="messages" id="messages"></div>
<div class="typing hidden" id="typing">Assistant is thinking…</div>
```

Empty `<div>` we append `<div class="msg user|bot|error">` nodes to. The
typing indicator gets `.hidden` removed during a request and re-added
after.

### Composer

```html
<form class="composer" id="composer" autocomplete="off">
  <textarea id="input" rows="1"></textarea>
  <button type="submit" id="send">Send</button>
</form>
```

`<textarea>` rather than `<input>` so users can paste multi-line
queries. The script auto-grows the textarea up to 160px.

### JavaScript

A single IIFE keeps the page state self-contained:

```js
const history = [];
```

In-memory only. Refresh = new conversation.

```js
const csrf = (document.cookie.match(/(?:^|; )csrf_access_token=([^;]+)/) || [])[1];

const resp = await fetch('/ai-chat/api/message', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    ...(csrf ? { 'X-CSRFToken': decodeURIComponent(csrf) } : {}),
  },
  credentials: 'same-origin',
  body: JSON.stringify({ message: trimmed, history }),
});
```

- `credentials: 'same-origin'` ensures the session cookie is sent so
  Flask-Login knows who the user is.
- The CSRF token is read from the cookie Superset's existing CSRF setup
  drops (`csrf_access_token`) and echoed in the `X-CSRFToken` header,
  matching what the rest of Superset expects on POST.

```js
inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    send(inputEl.value);
  }
});
```

Standard chat UX: Enter sends, Shift+Enter inserts a newline.

---

## `requirements-local.txt`

```
google-genai>=1.0.0
```

That's the only Python dep we add on top of what Superset already ships.
`docker-bootstrap.sh` reinstalls this file on every container start
([`docker/docker-bootstrap.sh:35`](../docker/docker-bootstrap.sh#L35)
and L59-65), so editing it = next restart picks up the change.

`mcp` itself is *not* listed — it comes in transitively via `fastmcp`
(in [`requirements/development.txt`](../requirements/development.txt)).

---

## `.env-local`

```
GEMINI_API_KEY=
# MOH_AI_MODEL=gemini-2.5-pro
# MCP_INTERNAL_URL=http://superset-mcp:5008/mcp
```

Read by docker compose for **every** Superset service via the `env_file:`
directive in [docker-compose.yml](../docker-compose.yml). The key only
matters for the `superset` service (where the chat handler runs), but
it's harmless on the others.

---

## Running it locally

### First-time setup

1. **Get a Gemini key** at <https://aistudio.google.com/apikey> — free
   tier gives ~10 requests/minute on `gemini-2.5-flash`, no billing
   setup required.

2. **Drop the key into `docker/.env-local`**:

   ```bash
   GEMINI_API_KEY=AIzaSy...your_key_here...
   ```

3. **Start the MCP server (if not already running)**:

   ```bash
   docker compose up -d superset-mcp
   ```

4. **Recreate the Superset web container** so it picks up the new
   env var. **Use `up -d --force-recreate`, not `restart`** —
   `docker compose restart` does not re-read `env_file:` directives,
   it only bounces the existing container with its already-baked env:

   ```bash
   docker compose up -d --force-recreate --no-deps superset
   docker compose logs -f superset
   ```

   First boot reinstalls `google-genai` and the editable Superset
   packages (~3-5 minutes on this image). Watch the log until you see
   `Registering blueprint: moh_ai_chat` followed by the Flask
   `Running on http://0.0.0.0:8088` line.

   You only need `--force-recreate` when env vars or `.env-local`
   change. Code-only edits (Python, templates) hot-reload via Flask's
   `--reload` flag without any container action.

5. **Open the page**: <http://localhost:8088/ai-chat/>

### Verifying it works

Try the **Health check** quick-prompt button. The expected reply mentions
the MCP server status. If you instead see:

| Symptom | Cause | Fix |
|---|---|---|
| Red banner: "Not configured" | `GEMINI_API_KEY` env var didn't reach the container — most often because `docker compose restart` was used after editing `.env-local` (which doesn't re-read env files). | `docker compose exec superset sh -c 'echo ${#GEMINI_API_KEY}'` should print a non-zero number. If it prints 0, run `docker compose up -d --force-recreate --no-deps superset` to force the container to re-read `.env-local`. |
| `admin only` toast on page load | Logged-in user isn't admin | Log in as admin, or grant the user the Admin role |
| Chat bubble: "AI request failed" | Look at `docker compose logs superset` — the full traceback is server-side | Most common: MCP container isn't running. `docker compose ps` should show `superset-mcp` Up |
| Chat bubble: "401" or auth issue | Session expired | Refresh; Flask-Login re-issues the cookie |
| Hangs > 60 seconds | Gemini reasoning loop, or rate-limited | Check the logs; if rate-limited, you'll see a `429` in the SDK output |
| Clicking Send does nothing, browser URL changes to `/ai-chat/?` | Inline script blocked by CSP — it has no nonce. The default `<button type="submit">` then submits the form natively as a GET, hence the trailing `?`. | Add `nonce="{{ macros.get_nonce() }}"` to every inline `<script>` in the template, and `{% import 'superset/macros.html' as macros %}` at the top of the file. CSP only needs nonces on `<script>`; `<style>` is allowed via `'unsafe-inline'` in [`superset/config.py:2179`](../superset/config.py#L2179). |
| 500 with `AttributeError: 'bool' object has no attribute 'items'` from `google/genai/_mcp_utils.py` | The Gemini SDK's MCP schema converter recurses into every JSON-Schema field but doesn't handle `additionalProperties: false` (a bool). Several Superset MCP tool schemas use this. | Already patched: `_patch_genai_for_bool_schemas()` in [`superset/moh_ai_chat.py`](../superset/moh_ai_chat.py) replaces the SDK function with a copy that returns scalars unchanged. Remove the patch when the SDK ships a fix upstream. |
| Gemini reports "I encountered an error" or "Unknown tool: 'run_code'" / 'run_query' / similar invented names | Tool search is on (default), so Gemini only sees `search_tools` / `call_tool` / pinned tools. Without seeing real names like `execute_sql` it hallucinates and the MCP server returns NotFoundError. | Already configured: [`superset/moh_branding.py`](../superset/moh_branding.py) sets `MCP_TOOL_SEARCH_CONFIG = {"enabled": False}` so every tool is advertised to the model directly. Costs ~15-20K extra tokens per turn but avoids the hallucination class entirely. |

---

## Adapting it

### Swap the model

Set `MOH_AI_MODEL=gemini-2.5-pro` in `.env-local`. Everything else
stays the same. The free-tier RPM is tighter on Pro — expect more
`429`s if the page is heavily used.

### Add fallback API keys (rotation on quota errors)

If a single free-tier key isn't enough, add additional keys as
`GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`, ... in `.env-local`. The
runtime tries them in order; if a request fails with a per-key
rate-limit / quota error (`429`, `quota`, `resource_exhausted`),
it rotates to the next key automatically. See
[`_ask_gemini`](../superset/moh_ai_chat.py) for the loop.

This **does not** help with `503` / "model overloaded" errors —
those are Gemini-wide and rotate-keys is bypassed for them
(see `_is_per_key_quota_error` in the same file).

ToS caveat: Google's free-tier terms aren't fond of multi-account
rotation. Fine for admin-only internal tools; risky for anything
user-facing.

### Open it up to non-admins

In [`superset/moh_ai_chat.py`](../superset/moh_ai_chat.py), change
`_require_admin()` to a weaker check, e.g.:

```python
def _require_login() -> tuple[Any, int] | None:
    if not getattr(current_user, "is_authenticated", False):
        return jsonify({"error": "unauthorized"}), 401
    return None
```

…and update the two call sites. **Be aware**: any logged-in user will
then be able to invoke `execute_sql` through MCP. Either tighten the
MCP server's RBAC enforcement (it's already on by default —
`MCP_RBAC_ENABLED = True` — so non-admins won't be able to run SQL
unless their role grants `can_execute_sql_query` on `SQLLab`), or trim
the visible tools via `MCP_TOOL_SEARCH_CONFIG` so the model can only
discover read-only ones.

### Swap Gemini for Claude (already wired up)

Set in `docker/.env-local`:

```
MOH_AI_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
# MOH_CLAUDE_MODEL=claude-sonnet-4-6   # optional, this is the default
```

Then `docker compose up -d --force-recreate --no-deps superset` so the new env
reaches the container. The page header will switch from
`Powered by gemini-2.5-flash` to `Powered by claude-sonnet-4-6`.

How it actually works: Anthropic's hosted-MCP feature requires a publicly
reachable URL (their servers fetch it), and our MCP runs on
`localhost:5008`. So `_ask_claude` does the same thing `_ask_gemini` does:

1. Open the local MCP session client-side
2. List MCP tools and convert them to Anthropic's `tools=[...]` format
3. Run the agent loop locally — when Claude returns `stop_reason="tool_use"`,
   forward each `tool_use` block through MCP via `session.call_tool()`,
   and pass the results back as `tool_result` blocks for the next turn
4. Return when Claude produces a final text answer (or hit the 12-iteration cap)

Why Claude is worth the cost for this workload:

- Far better at strict tool schemas — no `MALFORMED_FUNCTION_CALL` failures
  on `generate_chart`'s 50+ field schema
- Better availability — no free-tier `503 overloaded` issues
- Cleaner multi-step reasoning ("look up dataset → inspect schema →
  generate chart" runs as one shot instead of needing prompt hand-holding)

Cost ballpark for this admin-tool usage: $1-5/month. Heavy use: $20-50.

### Swap Gemini for OpenAI (already wired up)

Set in `docker/.env-local`:

```
MOH_AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
# MOH_OPENAI_MODEL=gpt-4o-mini   # optional, this is the default
```

Then `docker compose up -d --force-recreate --no-deps superset`.

`_ask_openai()` uses chat-completions with native function calling. The
MCP server tools are presented as `{"type": "function", "function": {...}}`
entries; when OpenAI returns `tool_calls` in a message, the loop forwards
each call through MCP via `session.call_tool()` and feeds the result back
as a `role="tool"` message in the next request.

Defaults to `gpt-4o-mini` (cheap, fast, solid tool calling). Override
with `MOH_OPENAI_MODEL=gpt-4o` for harder reasoning, or `gpt-4.1` family
when available.

OpenAI's hosted-MCP feature (passing `{"type": "mcp", "server_url": ...}`
in the Responses API) requires a publicly reachable URL — would need a
tunnel like ngrok or cloudflared for localhost. We use the chat-completions
client-side path instead so it works against `localhost:5008` directly.

### Inline chart embeds

When the AI's reply contains a Superset URL (e.g. `/explore/?form_data_key=...`
returned by `generate_explore_link` or `generate_chart`), the chat UI scans
the text and appends an `<iframe>` rendering the chart inline beneath the
bubble. The iframe loads with `?standalone=3` so only the chart canvas shows
— no Superset top nav, side panel, or filter bar.

Implementation lives entirely in [`superset/templates/superset/ai_chat.html`](../superset/templates/superset/ai_chat.html):

- `extractEmbedUrls(text)` — regex scans the bot reply for any `/explore/`,
  `/dashboard/`, or `/sqllab/` URL.
- `appendChartEmbed(rawUrl)` — adds `standalone=3`, builds the iframe, and
  drops a "Open full view ↗" link below it.

Why this works without extra config:

- The AI Assistant page and the embed URL share the **same origin** (e.g.
  `localhost:8090`), so Talisman's default `X-Frame-Options: SAMEORIGIN`
  permits the embed.
- The user's Superset session cookie carries into the iframe automatically,
  so RBAC still applies — you can't see a chart you wouldn't see in a normal tab.
- CSP `frame-ancestors` defaults to `default-src 'self'` — same-origin frames OK.

Caveat: the URL the AI returns must point at the user-facing Superset
hostname/port, not the internal docker service name. This is why
[`superset/moh_branding.py`](../superset/moh_branding.py) sets
`WEBDRIVER_BASEURL_USER_FRIENDLY = "http://localhost:8090/"`. If you change
`SUPERSET_PORT`, update that too (or set the `MOH_PUBLIC_URL` env var).
The MCP server reads that config at startup, so restart `superset-mcp`
after changing it.

### Stream responses

Drop the single-shot `generate_content` call and use
`client.aio.models.generate_content_stream` instead. The route handler
becomes a Server-Sent Events generator instead of returning JSON. The
JS side switches `fetch` for `EventSource` (or a fetch + reader). About
60 lines of additional code — not done in v1 because the perceived-latency
win is small for short answers.

### Persist conversations

Add a small SQLAlchemy model in `superset/moh_ai_chat.py` (e.g.
`AiChatMessage(user_id, role, content, created_on)`), a migration in
`superset/migrations/versions/...`, and write each turn from the route
handler. Then load history on page render and remove the
browser-keeps-history hack.

---

## Security notes

- **API key**: never sent to the browser. Lives in `docker/.env-local`
  (gitignored) and is read by `os.environ` server-side.
- **CSRF**: enforced by Flask-WTF on the POST endpoint via the standard
  Superset CSRF setup. The JS reads the `csrf_access_token` cookie and
  echoes it back in `X-CSRFToken`.
- **RBAC**: the MCP server applies Superset's full RBAC stack to every
  tool call. Even though the AI Assistant page is admin-gated, the
  MCP server still enforces permissions independently — defense in
  depth.
- **Audit log**: every tool call lands in **Settings → Action Log** as
  `mcp.<tool_name>.<phase>`, attributed to the configured MCP user (by
  default `MCP_DEV_USERNAME = "admin"` from
  [`superset/moh_branding.py`](../superset/moh_branding.py)).
- **Prompt-injection caveat**: Gemini reads the *contents* of MCP tool
  responses (e.g. dashboard descriptions, dataset names, SQL results).
  If a hostile user can write arbitrary text into one of those fields,
  they could try to manipulate the model. Mitigations: keep the page
  admin-only, keep `MCP_RBAC_ENABLED = True`, and log everything.

---

## Going to production

This v1 is fine for an internal admin tool on a trusted network. Before
exposing it publicly:

1. **Enable JWT auth on the MCP server** (currently `MCP_AUTH_ENABLED = False`
   in [`superset/moh_branding.py`](../superset/moh_branding.py)). See
   [`docs/admin_docs/configuration/mcp-server.mdx`](./admin_docs/configuration/mcp-server.mdx#L149)
   for the three options (JWKS, static RSA key, or HS256 secret).
2. **Add per-user rate limiting** in front of `/ai-chat/api/message` —
   even a simple Flask-Limiter rule prevents one user from burning the
   whole Gemini quota.
3. **Move the API key to a secrets manager** (Vault, AWS Secrets Manager,
   Kubernetes secret) instead of `.env-local`.
4. **Enable streaming** so users see partial responses for long queries
   — the perceived-latency improvement is significant on Pro models.
5. **Persist conversations** if you want users to come back to prior
   sessions or for compliance review.

---

## Why this shape (and what I considered)

A few "why didn't you ..." answers:

- **Why a custom blueprint instead of a Superset extension?**
  Extensions (`.supx`) are richer but require a build step, a manifest,
  and Webpack Module Federation. Overkill for one admin-only page.
  When a second AI-related page is added, that's the time to migrate.

- **Why HTML/JS instead of a React component in `superset-frontend`?**
  Same reason — adding a new route to the SPA means touching the
  webpack config, route table, and Redux side. The blueprint route
  bypasses all of that and is independently deployable.

- **Why per-request MCP sessions instead of a pool?**
  Simpler code, no cross-request state, handshake is cheap (~50 ms
  locally). If the page becomes hot-path enough to matter, a pool is
  ~30 lines.

- **Why store history client-side?**
  Avoids a new DB table, a migration, a cleanup job, and a privacy
  question (chat content can be sensitive). Refresh = fresh start is
  the right default for an admin tool.

- **Why no streaming in v1?**
  Streaming is a meaningful complexity bump (SSE or chunked transfer
  encoding, generator-based handler, JS reader-loop). For
  short-question / short-answer admin chats, the perceived-latency win
  is small. Trivial to add later.
