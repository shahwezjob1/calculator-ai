import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from calculator_agent.core.dependencies import get_thread_service
from calculator_agent.modules.calculator.dto.threads import ThreadMessagesResponse, ThreadsResponse
from calculator_agent.modules.calculator.service.thread_service import ThreadService

router = APIRouter(prefix="/calculator", tags=["Threads"])
logger = logging.getLogger(__name__)


@router.get("/threads", response_model=ThreadsResponse)
async def list_threads(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    thread_service: ThreadService = Depends(get_thread_service),
):
    logger.info("Controller request started: list_threads page=%s size=%s", page, size)
    return await thread_service.list_threads(page, size)


@router.get("/threads/{thread_id}/messages", response_model=ThreadMessagesResponse)
async def get_thread_messages(
    thread_id: UUID,
    thread_service: ThreadService = Depends(get_thread_service),
):
    logger.info("Controller request started: get_thread_messages thread_id=%s", thread_id)
    return await thread_service.get_messages(thread_id)
