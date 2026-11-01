import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from calculator_reviewer.core.exceptions.llm_unavailable_exception import LlmUnavailableException
from calculator_reviewer.modules.review.dto.generate_request import GenerateRequest
from calculator_reviewer.modules.review.dto.generate_response import GenerateResponse
from calculator_reviewer.modules.review.dto.param_descriptor import ParamDescriptor
from calculator_reviewer.modules.review.service.prompts import GENERATE_SYSTEM_PROMPT


class LlmGeneratedParam(BaseModel):
    name: str
    description: str


class LlmGeneratedCalculation(BaseModel):
    name: str
    description: str
    script: str
    params: list[LlmGeneratedParam] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _format_generate_request(request: GenerateRequest) -> str:
    lines = [f"Request: {request.prompt}"]
    if request.name:
        lines.append(f"Required name: {request.name}")
    if request.params_hint:
        lines.append("Param hints:")
        lines.extend(f"- {p.name}: {p.description}" for p in request.params_hint)
    return "\n".join(lines)


class GenerateService:
    logger = logging.getLogger(__name__)

    def __init__(self, review_model: BaseChatModel):
        self._structured_model = review_model.with_structured_output(LlmGeneratedCalculation)

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        self.logger.debug("Generating calculation script: name=%s", request.name)
        try:
            outcome: LlmGeneratedCalculation = await self._structured_model.ainvoke(
                [
                    SystemMessage(content=GENERATE_SYSTEM_PROMPT),
                    HumanMessage(content=_format_generate_request(request)),
                ]
            )
        except Exception as exc:
            raise LlmUnavailableException("LLM generation call failed") from exc
        return GenerateResponse(
            # The model adapts a provided display-style name into a valid snake_case
            # identifier (prompt rule); honoring request.name verbatim would let names
            # through that calculator-service rejects at save time.
            name=outcome.name,
            description=outcome.description,
            script=outcome.script,
            params=[ParamDescriptor(name=p.name, description=p.description) for p in outcome.params],
            notes=outcome.notes,
        )
