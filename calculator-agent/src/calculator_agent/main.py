from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from calculator_agent.core.clients.calculations_api_client import CalculationsApiClient
from calculator_agent.core.clients.constants_api_client import ConstantsApiClient
from calculator_agent.core.clients.reviewer_api_client import ReviewerApiClient
from calculator_agent.core.config import settings
from calculator_agent.core.exceptions.global_exception_handler import register_exception_handlers
from calculator_agent.core.logging_config import configure_logging
from calculator_agent.modules.calculator.agent.graph import build_agent
from calculator_agent.modules.calculator.controller.chat_controller import router as chat_router
from calculator_agent.modules.calculator.controller.thread_controller import router as thread_router

configure_logging()

# TODO: SSE streaming endpoint (POST /api/v1/calculator/chat/stream)
# TODO: tests under calculator-agent/tests/
# TODO: in-tool interrupt() HITL gate on save_calculation (deferred by decision)
# TODO: guard custom constants whose name collides with universal constants
#       (pi, e, function names) when rows were inserted directly via SQL


@asynccontextmanager
async def lifespan(app: FastAPI):
    # AsyncPostgresSaver requires autocommit, pipeline-free, dict_row connections.
    pool = AsyncConnectionPool(
        settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    await pool.open()
    checkpointer = AsyncPostgresSaver(pool)
    store = AsyncPostgresStore(pool)
    await checkpointer.setup()  # idempotent: LangGraph's own tables
    await store.setup()
    service_http = httpx.AsyncClient(
        base_url=settings.calculator_service_url, timeout=httpx.Timeout(10.0, read=30.0)
    )
    # Generous read timeout: the author loop is up to ~6 LLM round trips.
    reviewer_http = httpx.AsyncClient(
        base_url=settings.reviewer_service_url, timeout=httpx.Timeout(10.0, read=300.0)
    )
    app.state.pool = pool
    app.state.agent = build_agent(
        checkpointer=checkpointer,
        store=store,
        constants_client=ConstantsApiClient(service_http),
        calculations_client=CalculationsApiClient(service_http),
        reviewer_client=ReviewerApiClient(reviewer_http),
    )
    yield
    await service_http.aclose()
    await reviewer_http.aclose()
    await pool.close()


app = FastAPI(title="calculator-agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api/v1")
app.include_router(thread_router, prefix="/api/v1")
register_exception_handlers(app)
