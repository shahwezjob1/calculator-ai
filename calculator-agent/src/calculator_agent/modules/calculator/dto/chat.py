from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


DecisionType = Literal["approve", "edit", "reject"]


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(min_length=1, max_length=10000)
    thread_id: UUID | None = Field(default=None, alias="threadId")


class PendingActionRequest(BaseModel):
    name: str
    args: dict[str, Any]
    description: str | None = None
    allowed_decisions: list[DecisionType] = Field(
        serialization_alias="allowedDecisions"
    )


class PendingAction(BaseModel):
    actions: list[PendingActionRequest]


class ChatMessageDto(BaseModel):
    role: Literal["tool_call", "tool_result"]
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


class ChatResponse(BaseModel):
    thread_id: UUID = Field(serialization_alias="threadId")
    answer: str | None = None
    pending_action: PendingAction | None = Field(
        default=None,
        serialization_alias="pendingAction",
    )
    messages: list[ChatMessageDto] = Field(default_factory=list)


class ResumeDecision(BaseModel):
    type: DecisionType
    args: dict[str, Any] | None = None
    feedback: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_decision(self) -> "ResumeDecision":
        if self.type == "edit" and self.args is None:
            raise ValueError("args is required when decision type is 'edit'")

        if self.type != "edit" and self.args is not None:
            raise ValueError("args is only allowed when decision type is 'edit'")

        return self


class ResumeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    thread_id: UUID = Field(alias="threadId")
    decisions: list[ResumeDecision] = Field(min_length=1)