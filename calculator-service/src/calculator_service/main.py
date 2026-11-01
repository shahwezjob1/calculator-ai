from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from psycopg_pool import AsyncConnectionPool

from calculator_service.core.clients.reviewer_api_client import ReviewerApiClient
from calculator_service.core.config import settings
from calculator_service.core.exceptions.global_exception_handler import register_exception_handlers
from calculator_service.core.logging_config import configure_logging
from calculator_service.modules.calculations.controller.calculation_controller import router as calculation_router
from calculator_service.modules.constants.controller.constant_controller import router as constant_router

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = AsyncConnectionPool(
        settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        open=False,
    )
    await pool.open()
    # Generous read timeout: a review is an LLM round trip.
    http_client = httpx.AsyncClient(
        base_url=settings.reviewer_service_url,
        timeout=httpx.Timeout(10.0, read=60.0),
    )
    app.state.pool = pool
    app.state.reviewer_client = ReviewerApiClient(http_client)
    yield
    await http_client.aclose()
    await pool.close()


app = FastAPI(title="calculator-service", lifespan=lifespan)


app.include_router(constant_router, prefix="/api/v1")
app.include_router(calculation_router, prefix="/api/v1")
register_exception_handlers(app)
