# ARCHITECTURE.md

How calculator-ai works at runtime. For file locations see [REPO_MAP.md](REPO_MAP.md);
for the reasoning behind these choices see the decision log in the root
[README.md](../README.md).

## System overview

```text
  calculator-ui (:3000, static HTML)
        │
        ▼
┌──────────────────────┐
│   calculator-agent   │ :8000  LangGraph agent, chat & threads, 14 tools,
│                      │        Postgres checkpointer + store, HITL interrupts
└─────┬──────────┬─────┘
      │          │
      ▼          ▼
┌──────────────┐  ┌──────────────────┐
│ calculator-  │─►│ calculator-      │ :8002  stateless LLM review,
│ service :8001│  │ reviewer         │        generation, author loop
└──────┬───────┘  └──────────────────┘
       ▼
  PostgreSQL (calculator-infra devcontainer, :5432)
```

Dependency rules: agent → service, agent → reviewer, service → reviewer. No cycles.
Each service owns its tables; cross-service access is REST only, through the typed
async clients in `core/clients/`.

| Component | Port | Owns |
|---|---|---|
| calculator-agent | 8000 | `threads` table + LangGraph checkpointer/store tables |
| calculator-service | 8001 | `custom_constants`, `custom_calculations` tables |
| calculator-reviewer | 8002 | nothing (stateless) |
| calculator-ui | 3000 | nothing (static file, talks to the agent) |

All services share the same error envelope:
`{"errors": [{"errorCode", "errorMessage", "details", "additionalInfo"}]}`.

## calculator-agent

### Agent assembly (`modules/calculator/agent/graph.py`)

`build_agent()` wires LangChain 1.x `create_agent` with:

- a Gemini chat model from `core/llm/factory.py` (`LLM_PROVIDER` / `LLM_MODEL`),
- 14 tools (below),
- a custom state schema: `AgentState` + `calculation_draft`,
- a dynamic system prompt middleware that appends "Known facts about the user"
  (long-term memories from the store, each shown with its key),
- `HumanInTheLoopMiddleware` gating `delete_calculation` and `delete_constant`
  (decisions: approve / edit / reject, batched mode),
- the Postgres checkpointer and store (API mode only).

Two run modes:

1. **FastAPI mode** — the lifespan opens one `AsyncConnectionPool`
   (autocommit, dict_row), runs `checkpointer.setup()` / `store.setup()`, creates the
   two shared `httpx.AsyncClient`s, and builds the agent once onto `app.state`.
2. **`langgraph dev` mode** — `make_graph()` builds the agent with NO checkpointer or
   store (the platform injects persistence) and no database at all; the API clients are
   created lazily from `.env` URLs (`core/clients/lazy.py`).

### The 14 tools (thin adapters)

| Tool | Does |
|---|---|
| `evaluate_expression` | the only way math happens; see Evaluator below |
| `remember_fact` / `forget_fact` | long-term memories in the LangGraph store, namespace `("memories",)` |
| `set_constant` / `delete_constant` / `search_constants` | constants via calculator-service (PUT / DELETE / bulk search; search returns names only) |
| `search_calculations` / `get_calculation` | lean bulk search; detail (description + params, script never shown to the model) |
| `execute_calculation` | runs a saved calculation with numeric params |
| `delete_calculation` | delete by name (interrupt-gated) |
| `author_calculation` | reviewer `/author` loop → draft into state (origin: new) |
| `load_calculation` | existing calculation → draft into state (origin: editing) |
| `revise_draft` | re-runs `/author` on the current draft with change instructions |
| `save_calculation` | persists the draft; interrupt-gated (see HITL) |

### The expression evaluator (`agent/evaluator.py`)

The model never computes. `evaluate_expression` runs a hand-written pipeline:

1. **Lexer** — char-by-char scan, whitespace-insensitive, parenthesis depth tracking,
   two-char operators (`**`, `//`), scientific-notation lookahead.
2. **Token whitelist** — every token must be a number (strict regex; rejects `inf`,
   `nan`, `1_000`, hex), an operator (`+ - * / // % **`), a paren/comma, a whitelisted
   function (`sqrt, abs, round, log, log10, exp, sin, cos, tan, factorial`), `pi`/`e`,
   or a custom constant name fetched fresh from `GET /constants/values`. First bad
   token → `Error: Invalid token ...` returned to the model.
3. **Guards** — token count, literal exponent cap, factorial cap.
4. **Evaluation** — the validated token string is evaluated with empty builtins and a
   namespace containing only the whitelisted functions and constant values. Safe by
   construction: no names outside the whitelist can survive validation and `.` is never
   a token, so attribute access is impossible. Results are normalized to ~12
   significant digits.

Custom constant values are resolved here, at evaluation time, from the database —
the model only ever handles constant NAMES.

### Conversation state and threads

- Per-thread conversation state lives in the Postgres **checkpointer**, keyed by
  `thread_id`; long-term memories live in the **store** (cross-thread).
- The `threads` table is the app-owned registry (LangGraph has no thread list or name
  concept) and the source of truth for thread existence (404s).
- New-thread flow in `ChatService`: create the row eagerly with a placeholder title
  (first 255 chars of the message) → run the agent and the title model concurrently
  (`asyncio.gather`; titles come from a separate cheap model, `TITLE_LLM_MODEL`) → on
  success patch the real title in; on failure delete the row. Eager creation means an
  interrupt during the very first message still has a thread row.

### HITL: interrupts and the resume protocol

Sensitive actions pause the run at runtime; prompts are not the enforcement mechanism.

- **Deletes** (`delete_calculation`, `delete_constant`): gated by
  `HumanInTheLoopMiddleware` before the tool executes.
- **Save** (`save_calculation`): an in-tool `interrupt()` whose payload carries the
  complete draft (name, description, params, script, review). Decisions: `approve`
  saves as-is; `edit` merges the user's edited fields and submits directly (no second
  approval cycle); `reject` keeps the draft and returns the user's feedback to the
  model. The draft is cleared only after a successful save.

API protocol: when a run pauses, `POST /chat` returns no `answer` and a
`pendingAction` of shape
`{actions: [{name, args, description, allowedDecisions}]}`. The client then calls
`POST /chat/resume` with `{threadId, decisions: [{type: approve|edit|reject, args?,
feedback?}]}` (`args` required for `edit`, forbidden otherwise). The response is shaped
like `/chat`, so chained interrupts work. Interrupts live in the checkpoint, so a
pending approval survives restarts and arbitrary delay.

### Agent API (`/api/v1/calculator`)

| Route | Purpose |
|---|---|
| `POST /chat` | `{message, threadId?}` → `{threadId, answer \| pendingAction, messages}`; `messages` carries the run's tool calls/results for UI transparency |
| `POST /chat/resume` | resume a paused run with decisions |
| `GET /threads?page&size` | paginated thread list (newest first) |
| `GET /threads/{id}/messages` | full history: user / assistant / tool_call / tool_result entries |
| `GET /health`, `/readiness` | probes |

CORS allows the UI origin (`http://localhost:3000`).

## calculator-service

### Constants (`modules/constants`)

A key-value resource, so one write verb:

| Route | Semantics |
|---|---|
| `PUT /api/v1/constants/{name}` | upsert |
| `DELETE /api/v1/constants/{name}` | delete (404 if missing) |
| `POST /api/v1/constants/search` | bulk: `{queries, size}` → per-query names + total (`""`/`*` = all) |
| `GET /api/v1/constants/values` | full name→value map (consumed by the agent's evaluator) |

Name rules (shared with calculations and params): `^[A-Za-z_][A-Za-z0-9_]*$`, max 64,
no `__`, must not collide with the universal names (`pi, e, result` + whitelisted
function names). Values must be finite.

### Calculations (`modules/calculations`)

| Route | Semantics |
|---|---|
| `POST /api/v1/calculations` | create (409 if name exists) |
| `PATCH /api/v1/calculations/{name}` | partial update, incl. optional rename (409 if new name taken) |
| `DELETE /api/v1/calculations/{name}` | delete |
| `POST /api/v1/calculations/search` | bulk, lean (name + description + total) |
| `GET /api/v1/calculations/{name}` | full detail incl. script and review notes |
| `POST /api/v1/calculations/{name}/execute` | `{params: {a: 1.0}}` → `{results, durationMs}` |

**Write pipeline** (create and every effective update): DTO + name/param validation →
static AST validation (`sandbox/script_validator.py`) → reviewer `POST /review`
(unreachable → 503 `REVIEWER_UNAVAILABLE`) → persist with `review_status`
`APPROVED` or, on an UNSAFE verdict, `FLAGGED` (saved but disabled; execute returns
409 `CALCULATION_DISABLED`; editing re-runs the pipeline and can re-enable). The full
review response is stored in `review_notes` (JSONB).

**Change detection on PATCH**: a no-op returns the row untouched; AST validation runs
only when script/params changed; the LLM review re-runs on ANY effective change
(name, description, script, or params — all are behavior-bearing in an agent system).

**Script contract**: params are injected as float variables; the script must assign
`result` (a number, or a dict of named numbers). Statements allowed: assignments,
if/elif/else, for over `range(...)`, while, break/continue; calls only to the
whitelisted functions; no imports, attributes, strings (except short result-dict
keys), lambdas, comprehensions, or dunder names.

**Execution sandbox** (`sandbox/script_executor.py` + `runner.py`): each execution
spawns `python -I runner.py` as a subprocess; JSON over stdin/stdout; the child
self-applies CPU and memory rlimits and executes with empty builtins plus the safe
namespace; the parent enforces a wall-clock timeout (`EXEC_TIMEOUT_SECONDS`, default
2s — an infinite loop is killed) and maps failures to `EXECUTION_TIMEOUT` /
`EXECUTION_FAILED` (422). Script bodies are never logged.

## calculator-reviewer

Stateless LLM endpoints (`REVIEW_LLM_MODEL` via `init_chat_model`, structured output):

| Route | Purpose |
|---|---|
| `POST /api/v1/review` | `{name, description, script, params}` → `{verdict: SAFE\|UNSAFE, issues: [{type: SAFETY\|CORRECTNESS\|QUALITY, message}], suggestedName, suggestedDescription, suggestedFixes}` |
| `POST /api/v1/generate` | prompt (+ optional name, paramsHint) → candidate `{name, description, script, params, notes}`; adapts display-style names to snake_case; output is never trusted — saves always re-run the write pipeline |
| `POST /api/v1/author` | the evaluator-optimizer loop: generate → review → regenerate against the issues; early exit when the verdict is SAFE with no SAFETY/CORRECTNESS issues; `maxIterations` 1–5 (default 3); returns the final draft + its review + iteration count |

Verdict policy: UNSAFE only for safety problems (resource abuse, constructs outside
the subset, unbounded loops) or a severe mismatch between the script and its
name/description. Quality nits stay SAFE with issues attached.

## End-to-end flows

**Simple math** — user: "what is (3+4)² / 7?" → agent calls
`evaluate_expression("( 3 + 4 ) ** 2 / 7")` → lexer + whitelist + eval → `7.0`.

**Custom constant** — "X1 stands for 5.5" → `set_constant` → PUT. Later, in any
thread: "X1 + 2" → evaluator fetches the values map → `7.5`. "What is X1?" is answered
by evaluating `X1`; values never enter the model's context.

**Author + save (HITL)** — "create a calculation for quadratic roots" →
`search_calculations` (duplicate check) → `author_calculation` → reviewer `/author`
loop → draft into state → agent calls `save_calculation` → in-tool interrupt →
`pendingAction` with the full draft → user approves (or edits) in the UI →
`/chat/resume` → POST to calculator-service → write pipeline re-reviews → saved
APPROVED (or FLAGGED + disabled, which the agent explains).

**Delete (HITL)** — "delete gp_sum" → middleware interrupts before the tool runs →
user approves / edits the name / rejects → tool executes (or not).

**Fix a flagged calculation** — `load_calculation` → `revise_draft` (review issues
included in the authoring prompt) → save interrupt → approve → re-review → APPROVED.

## Configuration

Each service reads `.env` via pydantic-settings (and `load_dotenv` for libraries that
read the environment directly).

| Service | Key variables |
|---|---|
| calculator-agent | `LLM_PROVIDER`/`LLM_MODEL`, `TITLE_LLM_PROVIDER`/`TITLE_LLM_MODEL`, `GOOGLE_API_KEY`, `DATABASE_URL`, `CALCULATOR_SERVICE_URL`, `REVIEWER_SERVICE_URL`, `SERVER_PORT=8000`, pool sizes, `LOG_LEVEL` |
| calculator-service | `DATABASE_URL`, `REVIEWER_SERVICE_URL`, `EXEC_TIMEOUT_SECONDS=2`, `EXEC_MEMORY_LIMIT_MB=128`, `SERVER_PORT=8001`, pool sizes, `LOG_LEVEL` |
| calculator-reviewer | `REVIEW_LLM_PROVIDER`/`REVIEW_LLM_MODEL`, `GOOGLE_API_KEY`, `SERVER_PORT=8002`, `LOG_LEVEL` |

Startup order: reviewer → service → agent. `startup.sh` in agent and service applies
SQL migrations (numeric version order, idempotent scripts) before starting uvicorn;
LangGraph's own tables are created by `setup()` in the agent lifespan.

## Error codes

| Code | HTTP | Raised by |
|---|---|---|
| `VALIDATION_FAILED` | 400 | all (request DTO validation, fields in `additionalInfo`) |
| `INVALID_NAME`, `INVALID_VALUE`, `INVALID_SCRIPT`, `INVALID_PARAMS` | 400 | service |
| `CONSTANT_NOT_FOUND`, `CALCULATION_NOT_FOUND`, `THREAD_NOT_FOUND` | 404 | service / agent |
| `CALCULATION_EXISTS`, `CALCULATION_DISABLED`, `NO_PENDING_ACTION` | 409 | service / agent |
| `EXECUTION_FAILED`, `EXECUTION_TIMEOUT` | 422 | service |
| `REVIEWER_UNAVAILABLE`, `LLM_UNAVAILABLE` | 503 | service / reviewer |
| `INTERNAL_ERROR` | 500 | all |
