import logging
import math
from uuid import UUID

from calculator_agent.core.constants import THREAD_NOT_FOUND_ERROR_CODE
from calculator_agent.core.exceptions.not_found_exception import NotFoundException
from calculator_agent.core.repo.thread_repository import ThreadRepository
from calculator_agent.modules.calculator.dto.pagination import Pagination
from calculator_agent.modules.calculator.dto.threads import (
    MessageDto,
    ThreadMessagesResponse,
    ThreadResponse,
    ThreadsResponse,
)
from calculator_agent.modules.calculator.service.chat_service import _content_to_text

_ROLE_BY_TYPE = {"human": "user", "ai": "assistant", "tool": "tool"}


class ThreadService:
    logger = logging.getLogger(__name__)

    def __init__(self, agent, thread_repository: ThreadRepository):
        self._agent = agent
        self._thread_repository = thread_repository

    async def list_threads(self, page: int, size: int) -> ThreadsResponse:
        threads, total = await self._thread_repository.find_all(page, size)
        return ThreadsResponse(
            threads=[ThreadResponse.from_entity(t) for t in threads],
            pagination=Pagination(page=page, size=size, total_items=total,
                                  total_pages=math.ceil(total / size)),
        )

    async def get_messages(self, thread_id: UUID) -> ThreadMessagesResponse:
        if not await self._thread_repository.exists(thread_id):
            raise NotFoundException(
                THREAD_NOT_FOUND_ERROR_CODE,
                f"Thread '{thread_id}' not found",
            )

        state = await self._agent.aget_state(
            {"configurable": {"thread_id": str(thread_id)}}
        )

        messages: list[MessageDto] = []

        for message in state.values.get("messages", []):
            if message.type == "human":
                content = _content_to_text(message.content)

                if content:
                    messages.append(
                        MessageDto(
                            role="user",
                            content=content,
                        )
                    )

            elif message.type == "ai":
                # An AIMessage can contain both tool calls and text.
                for tool_call in getattr(message, "tool_calls", []) or []:
                    messages.append(
                        MessageDto(
                            role="tool_call",
                            tool_name=tool_call.get("name"),
                            tool_call_id=tool_call.get("id"),
                            args=tool_call.get("args") or {},
                        )
                    )

                content = _content_to_text(message.content)

                if content:
                    messages.append(
                        MessageDto(
                            role="assistant",
                            content=content,
                        )
                    )

            elif message.type == "tool":
                content = _content_to_text(message.content)

                messages.append(
                    MessageDto(
                        role="tool_result",
                        content=content or None,
                        tool_name=getattr(message, "name", None),
                        tool_call_id=getattr(message, "tool_call_id", None),
                    )
                )

        return ThreadMessagesResponse(
            thread_id=thread_id,
            messages=messages,
        )