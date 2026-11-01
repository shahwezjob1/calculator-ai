"""Lazily constructed default clients for runs outside the FastAPI lifespan
(`langgraph dev` / LangGraph Studio). URLs come from .env via settings; the
clients are created on first use and reused for the process lifetime."""

import httpx

from calculator_agent.core.clients.calculations_api_client import CalculationsApiClient
from calculator_agent.core.clients.constants_api_client import ConstantsApiClient
from calculator_agent.core.clients.reviewer_api_client import ReviewerApiClient
from calculator_agent.core.config import settings

_service_http: httpx.AsyncClient | None = None
_reviewer_http: httpx.AsyncClient | None = None


def _service_client() -> httpx.AsyncClient:
    global _service_http
    if _service_http is None:
        _service_http = httpx.AsyncClient(
            base_url=settings.calculator_service_url, timeout=httpx.Timeout(10.0, read=30.0)
        )
    return _service_http


def _reviewer_http_client() -> httpx.AsyncClient:
    global _reviewer_http
    if _reviewer_http is None:
        # Generous read timeout: the author loop is up to ~6 LLM round trips.
        _reviewer_http = httpx.AsyncClient(
            base_url=settings.reviewer_service_url, timeout=httpx.Timeout(10.0, read=300.0)
        )
    return _reviewer_http


def default_constants_client() -> ConstantsApiClient:
    return ConstantsApiClient(_service_client())


def default_calculations_client() -> CalculationsApiClient:
    return CalculationsApiClient(_service_client())


def default_reviewer_client() -> ReviewerApiClient:
    return ReviewerApiClient(_reviewer_http_client())
