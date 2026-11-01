# calculator-ai

An AI-powered calculator built as a **Python FastAPI microservices system**: User can give prompts asking the agent to perform calculations, create custom constants and short scripts and execute them with the help of the agent. It contains a small HTML UI for better visualisation and interaction with the agent. It combines a LangChain/LangGraph conversational agent, a domain service, and an LLM-based service for generating and reviewing custom calculation scripts. The project demonstrates practical Python microservice and AI-agent engineering, along with the key design decisions and trade-offs. (see [How the design evolved](#how-the-design-evolved)).

## Tech stack

- Python 3.12 · FastAPI · uv
- LangChain 1.x / LangGraph (Postgres checkpointer + store) with Gemini
- VS Code devcontainers 
- Claude Code was used as an implementation assistant during development

## What it does

Talk to the agent like a person:

- *"What is 3 plus 4 squared divided by 7?"* → the agent translates the question into a validated expression and computes it with a tool — the LLM never does mental math.
- *"Remember that X1 stands for 5.5"* → stored as a **custom constant**; later, *"what is X1 + 2?"* works in any conversation — and the agent uses the constant **by name**, so the value always comes fresh from the database, never from the model's memory.
- *"Create a calculation that solves quadratic equations"* → the agent has code **generated** (it never writes code itself), the script passes static AST validation and an LLM review, and is stored as a reusable **custom calculation** — then *"solve x² + 5x + 6 = 0"* executes it in a resource-limited sandbox.
- *"Always round results to two decimals"* → long-term memory, honored across all future conversations.

## System architecture

```text
                      ┌──────────────────────┐
         users ─────► │   calculator-agent   │  :8000   LangChain 1.x agent, chat & threads,
                      │  (AI orchestration)  │          14 tools, Postgres checkpointer/store
                      └─────┬──────────┬─────┘
                            │          │
                 REST/httpx │          │ REST/httpx
                            ▼          ▼
         ┌──────────────────────┐   ┌──────────────────────┐
  users► │  calculator-service  │──►│ calculator-reviewer  │  :8002   stateless LLM
         │   (domain)           │   │  (review + codegen)  │          review & generation
         └──────────┬───────────┘   └──────────────────────┘
              :8001 │
                    ▼
              PostgreSQL (devcontainer)
```

The dependency graph is a strict **DAG** — `agent → service`, `agent → reviewer`, `service → reviewer` — no cycles, by design (see decision log).

| Service | Port | Role | Owns (data) |
|---|---|---|---|
| `calculator-agent` | 8000 | Agent orchestration: chat, conversation threads, tools, memory | `threads` table, LangGraph checkpointer/store tables |
| `calculator-service` | 8001 | Domain: custom constants + custom calculations, sandboxed script execution | `custom_constants`, `custom_calculations` tables |
| `calculator-reviewer` | 8002 | Stateless AI utility: script safety/quality review, script generation | (no DB) |
| `calculator-ui` | 3000 | Single-file HTML chat UI that talks to the agent (approvals included) | — |
| `calculator-infra` | — | Dev environment: pinned Postgres devcontainer, persisted data, SQL workspace | — |

**Hard rule:** services never touch each other's tables. All cross-service access goes through REST APIs via typed async HTTP clients. One Postgres instance, strict table ownership.

Deeper runtime detail (flows, HITL protocol, sandbox, error codes) lives in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); the file-by-file layout is in [docs/REPO_MAP.md](docs/REPO_MAP.md).

## The services in brief

### calculator-agent
- evaluates mathematical expressions using supported operators, functions, built-in constants, and stored custom constants.​‌
- remembers and forgets user preferences across all conversations​‌
- upsert, bulk search and delete (through HITL) custom constants created by user​‌
- bulk searches, creates (via HITL) and deletes (via HITL) custom calculation scripts based on users requirements 
- provides list of threads and message history per thread including tool calls and results
- human-in-the-loop approvals: approve, edit, or reject before anything is saved or deleted
- exports bare Agent (no persistence, no DB) for `langgraph dev` / LangGraph Studio.

### calculator-service
- Crud Apis to bulk search upsert and delete custom constants
- Crud Apis to bulk search create update delete custom calculation scripts
- sandboxed subprocess to execute scripts with wall clock timeout, limited memory and static AST allowlist for scripts

### calculator-reviewer
- Acts as the advisor and quality gate. 
- Stateless LLM endpoints Consumed by the service's write pipeline and by the agent's generate tool
- `POST /review` (structured verdict + issues + suggested description/fixes)
- `POST /generate` (natural-language prompt → candidate script + params + description)
- `POST /author` (the evaluator-optimizer loop that generates, reviews, and regenerates against the review's issues until clean or the iteration cap, returning the final draft with its review) 

## Running locally

1. Open `calculator-infra/` in a VS Code devcontainer ("Dev Containers: Open Folder in Container") — pinned Postgres starts, port 5432 forwarded, data persisted in `calculator-infra/data/` (gitignored). The container's workspace is `sql/`, a committed set of inspection queries.
2. In each service folder: `uv sync`, copy `.env.example` → `.env` (add your `GOOGLE_API_KEY`).
3. Start in dependency order: reviewer (`:8002`) → service (`:8001`, `startup.sh` applies its SQL migrations) → agent (`:8000`, likewise).
- Open Calculator AI in VS Code
- Install [Python 3.12+] and UV
- Open new terminal for each service

```
cd calculator-reviewer 
uv run uvicorn calculator_reviewer.main:app --reload --port 8002
```
```
cd calculator-service
uv run ./startup.sh
```
```
cd calculator-agent
uv run ./startup.sh
```
```
cd calculator-ui
python3 -m http.server 3000
```
To expose agent to Langsmith Studio
```
cd calculator-agent
uv run langgraph dev
```

4. Open the application and API documentation:

   - **Web UI:** [http://localhost:3000/calculator-ui.html](http://localhost:3000/calculator-ui.html)
   - **Agent Swagger:** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Calculator Service Swagger:** [http://localhost:8001/docs](http://localhost:8001/docs)
   - **Calculator Reviewer Swagger:** [http://localhost:8002/docs](http://localhost:8002/docs)

## How the Design Evolved

This project was planned decision-by-decision before any code was written. Each entry captures a problem, the chosen solution, why it was chosen, and the alternative that was considered. The decisions are grouped by theme.

### System architecture and service boundaries

#### 1. Microservice instead of Monolith and Service Boundaries Based on Ownership and Scaling

**Problem:** Define meaningful service boundaries.

**Chosen:** Agent, Domain Service, and Reviewer Service.

**Why:** Domain ownership and scaling characteristics align naturally.

**Alternative:** Split services based only on technical concerns.

---

#### 2. Dedicated Reviewer Service

**Problem:** Both the agent and service need script review and generation.

**Chosen:** Stateless `calculator-reviewer` service.

**Why:** Both the agent and the domain service need review and generation. Putting it inside either one would create a circular dependency between services, so it was extracted into its own stateless service. It also keeps the main agent's scope small — it never writes script code itself, which means fewer hallucinations and mistakes.

---

#### 3. Consistent Service Architecture

**Problem:** Keep all services easy to understand and maintain.

**Chosen:** Controller → Service → Repository layering.

**Why:** Clear separation of responsibilities and familiar enterprise structure.

---

#### 4. Async-First Architecture

**Problem:** Most agent time is spent waiting on LLM, database, and HTTP calls.

**Chosen:** Fully async implementation.

**Why:** Better concurrency, natural fit for LangChain, and required for future response streaming.

**Alternative:** Traditional synchronous endpoints.

---

### Agent design and tool interface

#### 5. Agent Architecture

**Problem:** Manage constants, calculations, and memory.

**Chosen:** One agent with multiple tools.

**Why:** Simpler architecture and better conversational context. Currently only 14 tools. Multi Agent and Mode based Agent architecture is chosen for larger number of tools with independent domains. Testing the agent showed no hallucination at current scale.

**Alternative:** Supervisor agent coordinating specialist sub-agents or Single Agent in different focus modes.

---

#### 6. Thin Tools

**Problem:** Avoid duplicated validation and business logic.

**Chosen:** Tools act as adapters over shared service code.

**Why:** Single source of truth.

**Alternative:** Separate implementations for tools and APIs.

---

#### 7. Bulk Search APIs

**Problem:** Agents often need multiple searches at once.

**Chosen:** Bulk search endpoints.

**Why:** Fewer tool calls, HTTP requests, and database round trips.

**Alternative:** One request per search term.

---

#### 8. Progressive Disclosure

**Problem:** Returning full calculation details wastes context.

**Chosen:** Search returns summaries; details are fetched separately.

**Why:** Smaller prompts and better tool selection.

**Alternative:** Always return full calculation data.

---

#### 9. Exposing Names Instead of UUIDs to the LLM

**Problem:** UUIDs are difficult for LLMs to use correctly.

**Chosen:** Name-based model-facing APIs.

**Why:** Easier for both humans and models.

**Alternative:** UUID-based contracts.

---

### Agent state and memory

#### 10. Database-Backed Conversation Memory

**Problem:** Conversations should survive restarts and be resumable.

**Chosen:** PostgreSQL-backed LangGraph checkpointer and store.

**Why:** Automatic conversation persistence with minimal custom code.

**Alternative:** In-memory storage or custom persistence implementation.

---

#### 11. Automatic Thread Titles

**Problem:** Users need meaningful conversation names.

**Chosen:** Generate titles using a lightweight model with a deterministic fallback.

---

#### 12. Drafts Stored in Agent State

**Problem:** LLMs are unreliable at copying scripts between tools.

**Chosen:** Store drafts in checkpointed agent state.

**Why:** No copying, no IDs, survives restarts.

**Alternative:** Pass full scripts through prompts or external draft storage.

---

### Agent reliability and safety

#### 13. Safe Expression Evaluation

**Problem:** Evaluate user-provided expressions safely.

**Chosen:** Custom lexer + strict token validation + restricted execution.

**Why:** Safe, predictable, and independent of LLM correctness.

**Better Alternative:** Stack based infix to postfix conversion and evaluation with whitelisted operators and mathematical functions and validation to prevent expressions with out of memory error. Same safety faster execution but more code and development time.

---

#### 14. Constant Values Hidden From the LLM

**Problem:** LLM-transcribed values can become wrong or stale.

**Chosen:** Only constant names are exposed to the model.

**Why:** Eliminates hallucinated or outdated values.

---

#### 15. Layered Sandbox Security

**Problem:** User-generated scripts must execute safely.

**Chosen:** AST validation + restricted execution + isolated subprocess.

**Why:** Security does not depend on a single protection layer.

**Alternative:** Rely on LLM review alone.

---

#### 16. Review Before Save by Design

**Problem:** Prevent saving unreviewed calculations.

**Chosen:** Save actions depend on reviewed draft state.

**Why:** Structural guarantee instead of relying on model behavior.

**Alternative:** Hide save tools until review is complete.

---

### Human-in-the-loop

#### 17. Interrupt-Based Human Approval

**Problem:** Sensitive actions require user approval.

**Chosen:** LangGraph interrupts with resume APIs.

**Why:** Survives restarts and integrates naturally with the UI.

**Alternative:** Conversational approval through chat messages.

---

#### 18. Runtime Enforcement Instead of Prompt Enforcement

**Problem:** Models may ignore instructions to ask for approval.

**Chosen:** Intercept actions at runtime.

**Why:** Guarantees approval enforcement.

**Alternative:** Depend on prompts alone.

---

### Data and persistence details

#### 19. How many APIs for Custom Constants

**Problem:** Constants are simple name → value resources.

**Chosen:** PUT for create/update and DELETE for removal.

**Why:** Matches common key-value store semantics.

**Alternative:** Separate create and update APIs.

---

#### 20. JSONB for Calculation Parameters

**Problem:** Calculations have flexible parameter definitions.

**Chosen:** Store parameters as JSONB.

**Why:** Simpler schema and natural ownership.

**Alternative:** Separate parameter tables.

---

#### 21. Numeric Migration Ordering

**Problem:** Perform DB migrations to update schemas.

**Chosen:** Simple startup script that runs SQL files in numeric version order (V2 before V10). SQL scripts are idempotent, so re-running them is safe.

**Why:** Plain alphabetical sorting gets this wrong (V10 sorts before V2), so the runner parses the version number and sorts numerically. Small, simple, no extra dependency.

**Alternative:** Use Flyway like migration tool.

## Roadmap (deliberately out of scope for v1)

- SSE streaming for chat responses - Currently out of scope because inference time is low
- Multi-agent supervisor variant (constants/calculations librarian) — as a comparative demo
- Mode-scoped dynamic tool exposure keyed on a `focus` state field (state-dependent action spaces) - Not required at current scale
- Fuzzy constant/calculation bulk search with caching via `pg_trgm`
- sympy-backed symbolic tools (equation solving beyond stored scripts) and stack based infix to postfix conversion and evaluation instead of sandboxed script execution - Deferred due to time and token constraints.

## Deferred Improvements

The following improvements have been intentionally deferred based on current project scope and implementation priorities due to time and Ai Token constraints :

- Expression evaluation currently executes within a restricted, sandboxed subprocess using execution time limits. A future enhancement would be to replace Python-based evaluation with a dedicated arithmetic parser and evaluator (for example, infix-to-postfix conversion followed by stack-based evaluation), eliminating the dependency on `eval()` entirely. This was deferred to prioritize delivery and reduce implementation complexity.

- Long-term memory currently uses a shared namespace. This is acceptable for the current deployment model, which is not intended for multi-user usage. User-scoped memory isolation should be introduced before supporting multiple users.

- The reviewer and calculator-service each enforce validation independently, which creates a risk of validation rule drift. The preferred long-term solution is to extract validation logic into a shared library consumed by both services, providing a single source of truth for all calculation validation rules. Also to ensure that the custom calculation script is fully functional we can let the llm run it with random parameter values during review apart from the validations.

- Database migrations are currently treated as idempotent and executed automatically based on migration naming conventions. As the platform evolves, migration history tracking and distributed locking mechanisms similar to Flyway should be introduced to provide stronger guarantees during concurrent startup and deployment scenarios.

- Reviewer-service failures are currently normalized to HTTP 503 responses. Future improvements may introduce centralized client error handling with explicit classification of retryable and non-retryable failures, similar to patterns commonly used with Spring Cloud OpenFeign, to provide better operational visibility and retry behavior.

- Calculation constants loaded from storage are currently allowed to override known scientific constants such as pi and e. A future improvement would be to reserve built-in mathematical constants and prevent their creation. Also adding api to bulk load only relevant custom constants.

- Bulk search currently uses one API request but executes separate database queries for each search term. SQL-level batching and query optimization are deferred for now and will be addressed in a future performance improvement.


