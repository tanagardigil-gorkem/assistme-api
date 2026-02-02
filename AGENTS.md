# Agent Guide (assistme-api)

This repository is a small FastAPI backend for the Assist Me app.
It is intentionally lightweight (no heavy tooling config yet), so agents should
follow the conventions already present in `app/` and `tests/`.

## Target stack

- **Python**: 3.13 (use modern typing + structured concurrency mindset)
- **FastAPI**: async-first endpoints; keep routers thin
- **Pydantic**: v2 models + `pydantic-settings` for configuration
- **LLM**: `langchain` with `langchain-openai` (OpenAI API key via env)

## Quickstart

- Create venv + install deps:
  - `python -m venv .venv`
  - `source .venv/bin/activate`
  - `pip install -r requirements.txt -r requirements-dev.txt`
- Run the API locally:
  - `uvicorn app.main:app --reload`

## Commands

### Run / Build

- Dev server: `uvicorn app.main:app --reload`
- Prod-ish server (no reload): `uvicorn app.main:app`

There is no explicit "build" step; treat "build" as:
- Import sanity: `python -m compileall app tests`
- Dependency sanity: `python -m pip check`

### Tests

- Run all tests: `pytest`
- Run with more output: `pytest -q` or `pytest -vv`

Run a single test (preferred forms):
- By node id:
  - `pytest tests/test_weather.py::test_weather_current_success`
- By file:
  - `pytest tests/test_weather.py`
- By name substring:
  - `pytest -k weather_current`

Async tests:
- `pytest.ini` sets `asyncio_mode = auto`, and tests typically use
  `@pytest.mark.asyncio`.

### Lint / Format

No linter/formatter is configured in this repo (no ruff/black/isort/mypy).
When editing, keep diffs small and match existing style.

Optional local tooling (only if you add it intentionally and consistently):
- `ruff` for lint/format
- `black` for formatting
- `isort` for import sorting
- `mypy` for static typing

## Agent-specific instructions files

- Cursor rules: none found (`.cursor/rules/` or `.cursorrules` do not exist).
- Copilot rules: none found (`.github/copilot-instructions.md` not present).

## Project layout

- `app/main.py`: FastAPI app factory + lifespan; installs a global http client.
- `app/api/v1/`: routers + endpoint modules.
- `app/services/`: pure-ish service functions (weather/news/dashboard).
- `app/schemas/`: Pydantic response/request models.
- `app/core/`: shared config, http utilities, and caching.
- `tests/`: pytest + httpx ASGITransport + respx mocks.

## Code style and conventions

### Imports

- Prefer absolute imports from `app...` (match existing code).
- Order imports in 3 blocks with a blank line between:
  - stdlib
  - third-party
  - local (app)
- In most non-endpoint modules, use `from __future__ import annotations`.
  - New modules under `app/` should include it unless there is a reason not to.

### Formatting

- Follow PEP 8-ish formatting; the repo looks "black-like" but is not enforced.
- Use trailing commas in multi-line argument lists/dicts.
- Keep endpoint signatures readable; wrap parameters across lines as needed.

### Types

- Use modern Python typing (3.10+): `X | None`, `list[str]`, etc.
- Prefer precise return types for service functions and helpers.
- Use Pydantic models for API I/O in `app/schemas/`.

### Naming

- Modules: `snake_case.py`.
- Functions: `snake_case`.
- Classes (Pydantic models): `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Private helpers: prefix with `_`.

### FastAPI patterns

- Endpoints live in `app/api/v1/endpoints/*.py` and expose an `APIRouter` named
  `router`.
- Use `Query(...)` validation for query params (bounds, lengths).
- Prefer `response_model=...` to keep responses stable and documented.
- Keep endpoints thin: parse inputs + call service functions.

### Service layer

- Put network/data-fetching logic in `app/services/...`.
- Services are async when doing I/O; keep them testable with respx.
- Favor pure transformation helpers (`_normalize_entry`, `_parse_datetime`, ...)
  that are easy to unit test.

### HTTP client usage

- Use the shared `httpx.AsyncClient` from `app.core.http.get_http_client()`.
- The client is created in `app.main.lifespan` via `create_http_client()`.
- For outbound HTTP, use `app.core.http.request_with_retries(...)`.

### Error handling

- Map upstream/network failures to `fastapi.HTTPException(status_code=502, ...)`.
  - Current pattern: include a short, non-sensitive detail string.
- Do not leak full upstream payloads, stack traces, or secrets into `detail`.
- If one upstream source failing should not fail the whole request (e.g. RSS
  feeds), catch and continue (see `app/services/news/rss.py`).

### Configuration

- Settings are in `app/core/config.py` (Pydantic Settings, env prefix
  `ASSISTME_`).
- `ASSISTME_CORS_ORIGINS` and `ASSISTME_RSS_FEEDS` accept either JSON arrays or
  comma-separated strings.
- Avoid reading env vars directly; use `get_settings()`.

### LLM / LangChain / OpenAI

**Goal:** keep LLM usage isolated, testable, and safe (no secret leakage).

- Put LLM logic behind a small service module (e.g. `app/services/llm/...`).
  - Endpoints should call a service function; services may call the LLM.
- Prefer the newer split packages:
  - `langchain` (core abstractions)
  - `langchain-openai` (OpenAI models)
  - `openai` (official client, if needed directly)
- API keys must come from environment variables (never hard-code).
  - Recommended setting name in this repo: `ASSISTME_OPENAI_API_KEY`.
  - Also support the standard `OPENAI_API_KEY` for compatibility.
  - Never log keys; if you must log configuration, redact secrets.

Recommended Settings fields (in `app/core/config.py`):

- `openai_api_key: str | None`
- `openai_model: str = "gpt-4o-mini"` (or whichever default you choose)
- `openai_timeout_s: float = 30.0`
- `openai_max_retries: int = 2`

Runtime pattern:

- Create model instances via dependency injection or a small factory.
- Do **not** create new LLM clients per request unless necessary.
- If a library call is **blocking/sync**, run it off the event loop
  (`anyio.to_thread.run_sync` or `asyncio.to_thread`).

### Pydantic v2 notes

- Prefer `BaseModel` + `model_config = ConfigDict(...)`.
- Use `field_validator` / `model_validator` (v2) instead of v1 validators.
- Keep API schemas stable: update response models deliberately.

### Secrets, safety, and logging

- Treat **all** credentials as secrets (OpenAI keys, upstream API tokens, cookies).
- Never commit secrets to git. Prefer:
  - local development: `.env` (gitignored) + `.env.example` (safe template)
  - deployed environments: secret managers (platform-native) + injected env vars
- Do not include user-provided sensitive content in logs unless required.
- When raising `HTTPException`, keep `detail` short and non-sensitive.
  - Never include prompts, full LLM outputs, or request bodies in `detail`.

### LangChain implementation conventions

- Keep prompt templates and structured outputs explicit.
  - Prefer Pydantic (or JSON Schema) structured output where possible.
  - Validate/normalize model output **before** returning it from an endpoint.
- Prefer small, composable chains (prompt → model → parser).
- Consider rate limiting and timeouts for endpoints that call LLMs.

### Caching

- Use `app.core.cache.make_ttl_cache(...)` for TTL caches.
- Cache keys should be small, hashable, and stable (tuples are common).

### Testing conventions

- Use `create_app()` to get an app instance.
- Use `httpx.ASGITransport(app=app)` + `httpx.AsyncClient` for requests.
- Mock outbound HTTP with `respx.mock`.
- Prefer deterministic tests (fixed payloads, no real network).

LLM tests:

- **Never** call the real OpenAI API from the test suite.
- Mock at the boundary:
  - For LangChain: monkeypatch the model's `ainvoke`/`invoke` (or the service function)
    to return a fixed response.
  - Keep golden outputs small and stable.

## When adding new code

- Prefer extending existing modules over introducing new dependencies.
- Keep public API shape stable (schemas + response models).
- If you must add a tool (ruff/black/etc.), also add config and document the new
  command(s) here.
