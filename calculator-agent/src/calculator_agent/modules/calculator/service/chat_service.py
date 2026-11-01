import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from calculator_agent.core.constants import (
    NO_PENDING_ACTION_ERROR_CODE,
    THREAD_NOT_FOUND_ERROR_CODE,
    VALIDATION_FAILED_ERROR_CODE,
)
from calculator_agent.core.exceptions.calculator_agent_exception import (
    CalculatorAgentException,
)
from calculator_agent.core.exceptions.conflict_exception import ConflictException
from calculator_agent.core.exceptions.not_found_exception import NotFoundException
from calculator_agent.core.repo.thread_repository import ThreadRepository
from calculator_agent.modules.calculator.dto.chat import (
    ChatMessageDto,
    ChatResponse,
    PendingAction,
    PendingActionRequest,
    ResumeDecision,
)
from calculator_agent.modules.calculator.service.title_service import TitleService



def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)


def _extract_pending_action(interrupt_value: Any) -> PendingAction:
    if not isinstance(interrupt_value, dict):
        raise CalculatorAgentException(
            VALIDATION_FAILED_ERROR_CODE,
            "Unsupported interrupt payload returned by the agent",
        )

    action_requests = interrupt_value.get("action_requests")
    review_configs = interrupt_value.get("review_configs")

    if not isinstance(action_requests, list) or not isinstance(review_configs, list):
        raise CalculatorAgentException(
            VALIDATION_FAILED_ERROR_CODE,
            "Invalid human-in-the-loop interrupt payload",
        )

    if len(action_requests) != len(review_configs):
        raise CalculatorAgentException(
            VALIDATION_FAILED_ERROR_CODE,
            "Interrupt actions and review configurations do not match",
        )

    actions: list[PendingActionRequest] = []

    for action_request, review_config in zip(
        action_requests,
        review_configs,
        strict=True,
    ):
        if not isinstance(action_request, dict):
            raise CalculatorAgentException(
                VALIDATION_FAILED_ERROR_CODE,
                "Invalid action request in interrupt payload",
            )

        if not isinstance(review_config, dict):
            raise CalculatorAgentException(
                VALIDATION_FAILED_ERROR_CODE,
                "Invalid review configuration in interrupt payload",
            )

        name = action_request.get("name")
        args = action_request.get("args")
        allowed_decisions = review_config.get("allowed_decisions")

        if not isinstance(name, str):
            raise CalculatorAgentException(
                VALIDATION_FAILED_ERROR_CODE,
                "Interrupt action is missing its tool name",
            )

        if not isinstance(args, dict):
            raise CalculatorAgentException(
                VALIDATION_FAILED_ERROR_CODE,
                f"Interrupt action '{name}' has invalid arguments",
            )

        if not isinstance(allowed_decisions, list):
            raise CalculatorAgentException(
                VALIDATION_FAILED_ERROR_CODE,
                f"Interrupt action '{name}' has no allowed decisions",
            )

        actions.append(
            PendingActionRequest(
                name=name,
                args=jsonable_encoder(args),
                description=action_request.get("description"),
                allowed_decisions=allowed_decisions,
            )
        )

    return PendingAction(actions=actions)

def _message_ids(messages: list[Any]) -> set[str]:
    return {
        str(message.id)
        for message in messages
        if getattr(message, "id", None) is not None
    }


def _extract_tool_messages(
    messages: list[Any],
    existing_message_ids: set[str],
) -> list[ChatMessageDto]:
    events: list[ChatMessageDto] = []

    for message in messages:
        message_id = getattr(message, "id", None)
        if message_id is not None and str(message_id) in existing_message_ids:
            continue

        if message.type == "ai":
            for tool_call in getattr(message, "tool_calls", []) or []:
                events.append(
                    ChatMessageDto(
                        role="tool_call",
                        tool_name=tool_call.get("name"),
                        tool_call_id=tool_call.get("id"),
                        args=jsonable_encoder(tool_call.get("args") or {}),
                    )
                )

        elif message.type == "tool":
            content = _content_to_text(message.content)
            events.append(
                ChatMessageDto(
                    role="tool_result",
                    content=content or None,
                    tool_name=getattr(message, "name", None),
                    tool_call_id=getattr(message, "tool_call_id", None),
                )
            )

    return events

class ChatService:
    logger = logging.getLogger(__name__)

    def __init__(self, agent, thread_repository: ThreadRepository, title_service: TitleService):
        self._agent = agent
        self._thread_repository = thread_repository
        self._title_service = title_service

    async def chat(
        self,
        message: str,
        thread_id: UUID | None,
    ) -> ChatResponse:
        if thread_id is not None and not await self._thread_repository.exists(thread_id):
            raise NotFoundException(
                THREAD_NOT_FOUND_ERROR_CODE,
                f"Thread '{thread_id}' not found",
            )

        new_thread = thread_id is None
        thread_id = thread_id or uuid4()
        config = {"configurable": {"thread_id": str(thread_id)}}

        existing_message_ids: set[str] = set()
        if not new_thread:
            current_state = await self._agent.aget_state(config)
            existing_message_ids = _message_ids(
                current_state.values.get("messages", [])
            )

        agent_input = {
            "messages": [HumanMessage(content=message)]
        }

        if new_thread:
            await self._thread_repository.create(
                thread_id,
                message[:255],
            )

            try:
                result, title = await asyncio.gather(
                    self._agent.ainvoke(agent_input, config),
                    self._title_service.generate(message),
                )
            except Exception:
                await self._thread_repository.delete(thread_id)
                raise

            if title != message[:255]:
                try:
                    await self._thread_repository.update_title(
                        thread_id,
                        title,
                    )
                except Exception:
                    self.logger.warning(
                        "Failed to update thread title for thread_id=%s",
                        thread_id,
                        exc_info=True,
                    )
        else:
            result = await self._agent.ainvoke(
                agent_input,
                config,
            )

        return self._to_response(thread_id, result, existing_message_ids)
    
    async def resume(
        self,
        thread_id: UUID,
        decisions: list[ResumeDecision],
    ) -> ChatResponse:
        if not await self._thread_repository.exists(thread_id):
            raise NotFoundException(
                THREAD_NOT_FOUND_ERROR_CODE,
                f"Thread '{thread_id}' not found",
            )

        config = {
            "configurable": {
                "thread_id": str(thread_id),
            }
        }

        state = await self._agent.aget_state(config)
        existing_message_ids = _message_ids(
            state.values.get("messages", [])
        )

        interrupts = [
            interrupt
            for task in state.tasks
            for interrupt in getattr(task, "interrupts", [])
        ]

        if not interrupts:
            raise ConflictException(
                NO_PENDING_ACTION_ERROR_CODE,
                f"Thread '{thread_id}' has no pending action to resume",
            )

        if len(interrupts) != 1:
            raise ConflictException(
                NO_PENDING_ACTION_ERROR_CODE,
                (
                    f"Thread '{thread_id}' has an unsupported "
                    "number of pending interrupts"
                ),
            )

        interrupt_value = interrupts[0].value
        resume_value = self._build_resume_value(
            interrupt_value,
            decisions,
        )

        result = await self._agent.ainvoke(
            Command(resume=resume_value),
            config,
        )

        return self._to_response(
            thread_id,
            result,
            existing_message_ids,
        )
        
    @staticmethod
    def _build_resume_value(
        interrupt_value: Any,
        submitted_decisions: list[ResumeDecision],
    ) -> dict[str, list[dict[str, Any]]]:
        if not isinstance(interrupt_value, dict):
            raise CalculatorAgentException(
                VALIDATION_FAILED_ERROR_CODE,
                "The pending interrupt has an unsupported format",
            )

        action_requests = interrupt_value.get("action_requests")
        review_configs = interrupt_value.get("review_configs")

        if not isinstance(action_requests, list) or not isinstance(review_configs, list):
            raise CalculatorAgentException(
                VALIDATION_FAILED_ERROR_CODE,
                "The pending interrupt is invalid",
            )

        if len(action_requests) != len(review_configs):
            raise CalculatorAgentException(
                VALIDATION_FAILED_ERROR_CODE,
                "The pending interrupt actions and review configurations do not match",
            )

        if len(submitted_decisions) != len(action_requests):
            raise ConflictException(
                NO_PENDING_ACTION_ERROR_CODE,
                (
                    f"Expected {len(action_requests)} decisions for the pending actions, "
                    f"but received {len(submitted_decisions)}"
                ),
            )

        decisions: list[dict[str, Any]] = []

        for action_request, review_config, submitted in zip(
            action_requests, review_configs, submitted_decisions, strict=True
        ):
            if not isinstance(action_request, dict):
                raise CalculatorAgentException(
                    VALIDATION_FAILED_ERROR_CODE,
                    "The pending action request is invalid",
                )

            if not isinstance(review_config, dict):
                raise CalculatorAgentException(
                    VALIDATION_FAILED_ERROR_CODE,
                    "The pending review configuration is invalid",
                )

            tool_name = action_request.get("name")
            original_args = action_request.get("args")
            allowed_decisions = review_config.get("allowed_decisions", [])

            if not isinstance(tool_name, str):
                raise CalculatorAgentException(
                    VALIDATION_FAILED_ERROR_CODE,
                    "The pending action is missing its tool name",
                )

            if not isinstance(original_args, dict):
                raise CalculatorAgentException(
                    VALIDATION_FAILED_ERROR_CODE,
                    f"The pending action '{tool_name}' has invalid arguments",
                )

            if submitted.type not in allowed_decisions:
                raise ConflictException(
                    NO_PENDING_ACTION_ERROR_CODE,
                    (
                        f"Decision '{submitted.type}' is not allowed for "
                        f"pending action '{tool_name}'"
                    ),
                )

            if submitted.type == "approve":
                decision: dict[str, Any] = {"type": "approve"}
                if submitted.feedback:
                    decision["message"] = submitted.feedback
                decisions.append(decision)
                continue

            if submitted.type == "reject":
                decisions.append({
                    "type": "reject",
                    "message": submitted.feedback or "The user rejected this action.",
                })
                continue

            edited_args = dict(original_args)
            edited_args.update(submitted.args or {})

            decision = {
                "type": "edit",
                "edited_action": {
                    "name": tool_name,
                    "args": edited_args,
                },
            }
            if submitted.feedback:
                decision["message"] = submitted.feedback

            decisions.append(decision)

        return {"decisions": decisions}

    def _to_response(
        self,
        thread_id: UUID,
        result: dict,
        existing_message_ids: set[str],
    ) -> ChatResponse:
        messages = result.get("messages", [])
        tool_messages = _extract_tool_messages(
            messages,
            existing_message_ids,
        )

        interrupts = result.get("__interrupt__") or []
        if interrupts:
            value = getattr(
                interrupts[0],
                "value",
                interrupts[0],
            )

            self.logger.info(
                "Chat paused on pending action: thread_id=%s",
                thread_id,
            )

            return ChatResponse(
                thread_id=thread_id,
                answer=None,
                pending_action=_extract_pending_action(value),
                messages=tool_messages,
            )

        answer = ""
        if messages:
            answer = _content_to_text(messages[-1].content)

        return ChatResponse(
            thread_id=thread_id,
            answer=answer,
            pending_action=None,
            messages=tool_messages,
        )
