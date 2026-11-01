import logging

from fastapi import APIRouter, Depends

from calculator_agent.core.dependencies import get_chat_service
from calculator_agent.modules.calculator.dto.chat import ChatRequest, ChatResponse, ResumeRequest
from calculator_agent.modules.calculator.service.chat_service import ChatService

router = APIRouter(prefix="/calculator", tags=["Chat"])
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    logger.info("Controller request started: chat thread_id=%s", request.thread_id)
    response = await chat_service.chat(request.message, request.thread_id)
    logger.info("Controller response ready: chat thread_id=%s pending=%s",
                response.thread_id, response.pending_action is not None)
    return response


@router.post("/chat/resume", response_model=ChatResponse)
async def resume(
    request: ResumeRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    logger.info(
        "Controller request started: resume thread_id=%s decisions=%s",
        request.thread_id,
        [decision.type for decision in request.decisions],
    )

    response = await chat_service.resume(
        request.thread_id,
        request.decisions,
    )

    logger.info(
        "Controller response ready: resume thread_id=%s pending=%s",
        response.thread_id,
        response.pending_action is not None,
    )
    return response
