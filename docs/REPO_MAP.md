# REPO_MAP.md

Where code lives and which service owns a change. All three services follow the same
layout: `src/<package>/core/` for shared infrastructure and `src/<package>/modules/`
for business features, with Controller → Service → Repository layering.

## Root

| Path | Purpose |
|---|---|
| `README.md` | Project overview, run instructions, and the 21-decision design log |
| `AGENTS.md` | Coding guidelines and conventions for AI coding agents |
| `CLAUDE.md` | Pointer to AGENTS.md |
| `docs/ARCHITECTURE.md` | Runtime behavior, flows, HITL protocol, error codes |
| `docs/REPO_MAP.md` | This file |
| `.gitignore` | Ignores `calculator-infra/data/`, `.env`, caches |

## calculator-infra/ — dev environment

| Path | Purpose |
|---|---|
| `.devcontainer/devcontainer.json` | Pinned Postgres devcontainer; runs the real Postgres entrypoint, forwards 5432, mounts `data/` and `init/`, opens the workspace in `sql/` |
| `data/` | Postgres data directory (persists across rebuilds; gitignored) |
| `init/` | First-boot SQL (runs once on an empty data dir) |
| `sql/` | Committed inspection queries (threads, checkpoints, store, constants, calculations) |

## calculator-ui/

| Path | Purpose |
|---|---|
| `calculator-ui.html` | Single-file chat UI; talks to the agent API, renders tool calls/results and the approve/edit/reject interrupt dialogs. Serve with `python3 -m http.server 3000` |

## calculator-agent/ — AI orchestration service (:8000)

| Path | Purpose |
|---|---|
| `pyproject.toml` | Dependencies (langchain/langgraph/psycopg/httpx) incl. Nexus quarantine pins |
| `.env.example` | Agent + title model vars, DB and service URLs |
| `startup.sh` | Applies migrations, then starts uvicorn |
| `Dockerfile` | Container build |
| `langgraph.json` | Exposes `make_graph` to `langgraph dev` / LangGraph Studio |
| `migrations/versions/V1__create_threads.sql` | `threads` table |

### src/calculator_agent/

| Path | Purpose |
|---|---|
| `main.py` | App, lifespan (pool, checkpointer/store setup, HTTP clients, agent build), CORS, routers; project TODOs |
| `core/config.py` | pydantic-settings; loads `.env` |
| `core/logging_config.py` | Plain-text parameterized logging |
| `core/constants.py` | This service's error codes |
| `core/migrations.py` | Numeric-order SQL migration runner (also `python -m` entrypoint) |
| `core/dependencies.py` | DI registry (agent, pool, repos, services) |
| `core/dto/` | Shared error envelope DTOs (Error, Errors, Info) |
| `core/exceptions/` | Exception hierarchy + global handlers |
| `core/entities/thread.py` | Thread dataclass |
| `core/repo/thread_repository.py` | Raw-SQL threads repo (create, exists, find_all, delete, update_title) |
| `core/llm/factory.py` | `build_chat_model()` (agent) and `build_title_model()` (titles) |
| `core/clients/` | Typed httpx clients: constants, calculations, reviewer; `errors.py` maps error envelopes; `lazy.py` builds clients from `.env` for `langgraph dev` |

### src/calculator_agent/modules/calculator/

| Path | Purpose |
|---|---|
| `controller/chat_controller.py` | `POST /chat`, `POST /chat/resume` |
| `controller/thread_controller.py` | `GET /threads`, `GET /threads/{id}/messages` |
| `service/chat_service.py` | Thread lifecycle (eager create + title patch), agent invoke, interrupt → `pendingAction`, resume with decisions |
| `service/title_service.py` | Title model call with truncated-prompt fallback |
| `service/thread_service.py` | Thread list + full message history (incl. tool calls/results) |
| `dto/chat.py` | ChatRequest/Response, PendingAction, ResumeRequest/Decision |
| `dto/threads.py` | Thread list + message DTOs |
| `dto/pagination.py` | Pagination DTO |
| `agent/graph.py` | `build_agent()` (model + tools + middleware + state schema), `make_graph()` for langgraph dev |
| `agent/prompts/v1_0.py` | The system prompt (versioned) |
| `agent/evaluator.py` | Expression lexer, token whitelist, guarded evaluation |
| `agent/tools/expression.py` | `evaluate_expression` |
| `agent/tools/memory.py` | `remember_fact`, `forget_fact` (LangGraph store) |
| `agent/tools/constants.py` | `set_constant`, `delete_constant`, `search_constants` |
| `agent/tools/calculations.py` | Search/get/execute/delete + draft lifecycle (author, load, revise, save with in-tool interrupt) |
| `agent/tools/__init__.py` | `get_tools()` registry (injected or lazy clients) |

## calculator-service/ — domain service (:8001)

| Path | Purpose |
|---|---|
| `pyproject.toml`, `.env.example`, `startup.sh`, `Dockerfile` | Project files (no langchain here) |
| `migrations/versions/V1__create_custom_constants.sql` | Constants table |
| `migrations/versions/V2__create_custom_calculations.sql` | Calculations table (params + review notes as JSONB) |

### src/calculator_service/

| Path | Purpose |
|---|---|
| `main.py` | App, lifespan (pool + reviewer HTTP client), routers |
| `core/config.py`, `core/logging_config.py`, `core/constants.py` | Settings; logging; error codes, name pattern, UNIVERSAL_NAMES |
| `core/migrations.py` | Same numeric-order migration runner |
| `core/dependencies.py` | DI registry |
| `core/dto/`, `core/exceptions/` | Error envelope + exception hierarchy/handlers |
| `core/entities/` | CustomConstant, CustomCalculation dataclasses |
| `core/repo/constant_repository.py` | Upsert, delete, bulk search, values map |
| `core/repo/calculation_repository.py` | Create, update (incl. rename), delete, find, bulk search |
| `core/clients/reviewer_api_client.py` | `POST /review` client (failures → 503) |

### src/calculator_service/modules/

| Path | Purpose |
|---|---|
| `constants/controller/constant_controller.py` | PUT/DELETE/{name}, POST /search, GET /values |
| `constants/service/constant_service.py` | Name/value validation (incl. `validate_identifier`, reused by calculations) |
| `constants/dto/` | Constant DTOs |
| `calculations/controller/calculation_controller.py` | CRUD + search + execute endpoints |
| `calculations/service/calculation_service.py` | Write pipeline (validate → AST → review → persist), change detection, execute orchestration |
| `calculations/sandbox/script_validator.py` | Static AST allowlist; requires a `result` assignment |
| `calculations/sandbox/script_executor.py` | Async subprocess runner with wall-clock timeout |
| `calculations/sandbox/runner.py` | Child-process entrypoint: rlimits, restricted namespace, result normalization |
| `calculations/dto/` | Calculation DTOs (requests, responses, search, execute) |

## calculator-reviewer/ — stateless LLM service (:8002)

| Path | Purpose |
|---|---|
| `pyproject.toml`, `.env.example`, `Dockerfile` | Project files (no DB, no migrations) |

### src/calculator_reviewer/

| Path | Purpose |
|---|---|
| `main.py` | App + routers |
| `core/config.py`, `core/logging_config.py`, `core/constants.py` | Settings, logging, error codes |
| `core/dependencies.py` | DI registry (review model via `lru_cache`) |
| `core/dto/`, `core/exceptions/` | Error envelope + handlers (incl. `LLM_UNAVAILABLE` → 503) |
| `core/llm/factory.py` | Review model via `init_chat_model` |
| `modules/review/controller/review_controller.py` | `POST /review`, `/generate`, `/author` |
| `modules/review/service/review_service.py` | Structured-output review (verdict + typed issues + suggestions) |
| `modules/review/service/generate_service.py` | Script generation targeting the subset contract |
| `modules/review/service/author_service.py` | Generate↔review loop with early exit and iteration cap |
| `modules/review/service/prompts.py` | SCRIPT_CONTRACT + review/generate system prompts |
| `modules/review/dto/` | Review/Generate/Author request + response DTOs |

## Common change locations

- **Add an agent capability (tool):** `agent/tools/` (+ register in `tools/__init__.py`),
  prompt rules in `agent/prompts/v1_0.py`, gate it in `agent/graph.py` if sensitive,
  document in `docs/ARCHITECTURE.md`.
- **Add a REST endpoint:** the owning service's `modules/<module>/controller/` +
  `service/` + `dto/`, wiring in `core/dependencies.py`.
- **Change cross-service communication:** `core/clients/` in the calling service only.
- **Database change:** a NEW idempotent script in that service's `migrations/versions/`
  (never edit an existing one) + `core/entities/` + `core/repo/`.
- **Change the script subset:** `script_validator.py` + `runner.py` namespace +
  reviewer `prompts.py` SCRIPT_CONTRACT + evaluator whitelists + `UNIVERSAL_NAMES` —
  all together; they are one shared contract.
- **Error codes:** the owning service's `core/constants.py` + handler mapping +
  the table in `docs/ARCHITECTURE.md`.
