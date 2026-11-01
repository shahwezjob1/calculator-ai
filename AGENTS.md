# AGENTS.md

## Purpose

This repository implements calculator-ai: an AI-powered calculator built as three FastAPI
microservices plus a small HTML UI. A LangChain/LangGraph agent (`calculator-agent`) chats
with users, evaluates expressions, and manages custom constants and custom calculation
scripts through REST calls to a domain service (`calculator-service`), which in turn uses a
stateless LLM service (`calculator-reviewer`) to generate and review scripts. PostgreSQL
(run via the `calculator-infra` devcontainer) stores conversations, long-term memory,
constants, and calculations.

This document explains how AI coding agents should work in this repository.

## Critical: Documentation Updates Required

Every change that adds files, modifies architecture, or changes business flows MUST include
updates to:

- `docs/REPO_MAP.md` — for new files, modules, or structure changes.
- `docs/ARCHITECTURE.md` — for API, flow, or behavior changes.
- `README.md` — when a design decision is added or reversed (the decision log is part of
  the project's value).

Do not consider a change complete until documentation is updated.

## General Working Principles

- Follow existing patterns before introducing new ones.
- Prefer modifying existing code over creating new abstractions.
- Keep changes focused and minimal; maintain consistency with nearby modules.
- Keep the Controller → Service → Repository layering intact in all three services.
- The three services communicate ONLY over REST through the typed clients in
  `core/clients/`. Never read or write another service's database tables.
- The dependency graph must stay a DAG: agent → service, agent → reviewer,
  service → reviewer. Never add a call in the other direction.
- Everything on a request path is async. Never put a blocking call in a handler, service,
  tool, or client; if a sync-only library is unavoidable, wrap it in `run_in_threadpool`.

## Before Making Code Changes

Review the relevant repository documentation first:

- [`docs/REPO_MAP.md`](docs/REPO_MAP.md) to find where code lives and which service owns
  the change.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) to understand flows, the HITL interrupt
  protocol, the sandbox, and component interactions.

## Tests

Do not add or modify test cases for now unless explicitly requested. These will be added
later separately.

## Layer Responsibilities

### Controllers

- Receive HTTP requests, validate inputs through FastAPI declarations and DTOs.
- Delegate business operations to services; return DTO responses.
- Must not contain business logic, access repositories or the database, or call other
  services directly.

### Services

- Business logic; coordinating repositories, API clients, the sandbox, and LLM calls.
- The primary location for business behavior.

### Repositories

- Persistence operations only, written as raw SQL over the shared async psycopg pool
  (`dict_row` cursors). No ORM. No business rules. No external calls.

### DTOs

- API request and response contracts with camelCase serialization aliases.
- Do not expose entities or internal dicts directly through APIs.

### Entities

- Plain dataclasses mapping database rows. Persistence models, not API contracts.

### API clients (`core/clients/`)

- The only place a service knows another service's wire format. Typed async methods over a
  shared `httpx.AsyncClient`; map error-envelope responses into clear exceptions or
  tool-visible messages. New cross-service calls go here, never inline in services/tools.

### Agent tools (`calculator-agent` only)

- Tools are thin adapters — "controllers for the LLM": typed signature + docstring +
  delegation to the evaluator, API clients, or the LangGraph store. No business logic.
- A tool docstring is the LLM-facing contract. This is the one exception to the minimal
  documentation rule: write tool docstrings carefully and keep them accurate.
- Tools that fail must RETURN a clear `"Error: ..."` string (not raise), so the model can
  self-correct.
- Tools that change the calculation draft return a `Command` updating `calculation_draft`
  in graph state plus a `ToolMessage`. `save_calculation` reads the draft from state via
  `InjectedState` and takes no content arguments — never add a path that lets the model
  pass script content directly to a save.

## Human-in-the-Loop Rules

- Destructive or persisting actions are gated at runtime, never by prompt alone:
  `delete_calculation` / `delete_constant` via `HumanInTheLoopMiddleware`, and
  `save_calculation` via an in-tool `interrupt()` that carries the full draft.
- The chat API surfaces a pause as `pendingAction`; `POST /chat/resume` carries the user's
  decisions (`approve` / `edit` / `reject`). Keep both shapes backward compatible — the UI
  depends on them.
- When adding a new sensitive tool, gate it the same way and document the payload shape in
  `docs/ARCHITECTURE.md`.

## Dependency Injection

All three services register dependencies in `core/dependencies.py` and inject them with
`Depends(...)`. Long-lived resources (connection pool, HTTP clients, the compiled agent)
are created once in the FastAPI lifespan and stored on `app.state`; services are cheap
per-request wrappers that receive collaborators through their constructors. Never construct
an agent, pool, or HTTP client inside a request handler or service constructor.

## Database Script Guidelines

- Migrations live in each service's `migrations/versions/` as `V<N>__<name>.sql` and are
  applied by `startup.sh` via `python -m <package>.core.migrations`.
- The runner sorts by the NUMERIC version (V2 before V10); filenames that do not match the
  pattern, or duplicate versions, fail startup loudly.
- Do not modify existing SQL scripts; add a new script for every change.
- Use additive, idempotent statements (`CREATE ... IF NOT EXISTS`,
  `ADD COLUMN IF NOT EXISTS`); scripts must be safe to run repeatedly.
- Timestamps: `TIMESTAMP` without timezone, stored in UTC,
  `NOT NULL DEFAULT CURRENT_TIMESTAMP` for `created_at` / `updated_at`.
- LangGraph's own checkpointer/store tables are created by `setup()` at agent startup —
  never write migrations for them.

## Safety Invariants (do not weaken)

- The model never computes: all arithmetic goes through `evaluate_expression`, whose lexer
  accepts only whitelisted tokens. `.` is never a valid standalone token.
- The model never authors script code: scripts come from the reviewer's `/author` loop and
  travel by reference in `calculation_draft`, never retyped by the model.
- Constant VALUES never reach the model: search returns names only; the evaluator resolves
  values from `GET /constants/values` at evaluation time.
- Scripts execute behind three independent layers: static AST allowlist at write time,
  restricted namespace, and a subprocess with wall-clock timeout and memory cap. The LLM
  review is a quality gate, never the security boundary.
- The universal names (`pi, e, result`, and the whitelisted function names) are a shared
  contract between the evaluator, the sandbox namespace, the reviewer prompts, and
  calculator-service name validation. Change them in all places together or not at all.

## Error Contract

All three services return the same envelope:
`{"errors": [{"errorCode", "errorMessage", "details", "additionalInfo": [{"property", "reason"}]}]}`
with descriptive codes (e.g. `INVALID_SCRIPT`, `CALCULATION_DISABLED`,
`EXECUTION_TIMEOUT`, `THREAD_NOT_FOUND`). The envelope DTOs and handler are duplicated per
service on purpose (shared contract, not a shared library). Each service's `core/constants.py`
carries only the codes it raises. Add new codes there and document them in
`docs/ARCHITECTURE.md`.

## Code Documentation Style

- Keep inline documentation minimal: brief single-line comments only when logic is
  non-obvious.
- Explain architecture, flows, and business logic in `docs/ARCHITECTURE.md`, not inline.
- Repository structure belongs in `docs/REPO_MAP.md`, not in module docstrings.
- Exception: agent tool docstrings (see Agent tools above).

## Logging Standards

- Use the shared logging configuration and a module logger; never `print()`.
- Keep logs plain text and parameterized.
- Never log prompts, model responses, script bodies, constant values, credentials, or API
  keys. Safe identifiers (thread id, calculation/constant name, review status) are fine.
- `INFO` for controller entry/exit; `DEBUG` for service internals.
- Log each failure at one owning boundary; do not log and re-raise the same error twice.

## Dependency Management

- All packages install from the Equinix Nexus PyPI mirror (configured in each
  `pyproject.toml`). Sync with `uv sync --system-certs`.
- The firewall quarantines very new releases. When a sync fails with a 403, probe for the
  newest allowed version with
  `uv pip install --system-certs --no-deps --target /tmp/probe --index-url <nexus simple> pkg==X`
  (curl probes are unreliable) and pin it under the "Transitive pins" comment in the
  affected `pyproject.toml`.
