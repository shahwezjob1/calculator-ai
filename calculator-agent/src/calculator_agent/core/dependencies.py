from functools import lru_cache

from fastapi import Depends, Request

from calculator_agent.core.llm.factory import build_title_model
from calculator_agent.core.repo.thread_repository import ThreadRepository
from calculator_agent.modules.calculator.service.chat_service import ChatService
from calculator_agent.modules.calculator.service.thread_service import ThreadService
from calculator_agent.modules.calculator.service.title_service import TitleService


def get_agent(request: Request):
    return request.app.state.agent


def get_pool(request: Request):
    return request.app.state.pool


@lru_cache
def get_title_model():
    return build_title_model()


def get_thread_repository(pool=Depends(get_pool)) -> ThreadRepository:
    return ThreadRepository(pool)


def get_title_service(title_model=Depends(get_title_model)) -> TitleService:
    return TitleService(title_model)


def get_chat_service(
    agent=Depends(get_agent),
    thread_repository: ThreadRepository = Depends(get_thread_repository),
    title_service: TitleService = Depends(get_title_service),
) -> ChatService:
    return ChatService(agent=agent, thread_repository=thread_repository, title_service=title_service)


def get_thread_service(
    agent=Depends(get_agent),
    thread_repository: ThreadRepository = Depends(get_thread_repository),
) -> ThreadService:
    return ThreadService(agent=agent, thread_repository=thread_repository)
