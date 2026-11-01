from datetime import datetime
from uuid import UUID
from typing import Any

from pydantic import BaseModel, Field

from calculator_agent.core.entities.thread import Thread
from calculator_agent.modules.calculator.dto.pagination import Pagination


class ThreadResponse(BaseModel):
    thread_id: UUID = Field(serialization_alias="threadId")
    thread_name: str = Field(serialization_alias="threadName")
    created_at: datetime = Field(serialization_alias="createdAt")

    @classmethod
    def from_entity(cls, entity: Thread) -> "ThreadResponse":
        return cls(thread_id=entity.thread_id, thread_name=entity.thread_name,
                   created_at=entity.created_at)


class ThreadsResponse(BaseModel):
    threads: list[ThreadResponse]
    pagination: Pagination


class MessageDto(BaseModel):
    role: str
    content: str | None = None
    tool_name: str | None = Field(
        default=None,
        serialization_alias="toolName",
    )
    tool_call_id: str | None = Field(
        default=None,
        serialization_alias="toolCallId",
    )
    args: dict[str, Any] | None = None


class ThreadMessagesResponse(BaseModel):
    thread_id: UUID = Field(serialization_alias="threadId")
    messages: list[MessageDto]
