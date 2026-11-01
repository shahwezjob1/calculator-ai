import logging
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from calculator_reviewer.core.exceptions.llm_unavailable_exception import LlmUnavailableException
from calculator_reviewer.modules.review.dto.review_request import ReviewRequest
from calculator_reviewer.modules.review.dto.review_response import ReviewIssue, ReviewResponse
from calculator_reviewer.modules.review.service.prompts import REVIEW_SYSTEM_PROMPT


class LlmReviewIssue(BaseModel):
    type: Literal["SAFETY", "CORRECTNESS", "QUALITY"]
    message: str


class LlmReviewResult(BaseModel):
    verdict: Literal["SAFE", "UNSAFE"]
    issues: list[LlmReviewIssue] = Field(default_factory=list)
    suggested_name: str | None = None
    suggested_description: str | None = None
    suggested_fixes: list[str] = Field(default_factory=list)


def _format_calculation(request: ReviewRequest) -> str:
    params = "\n".join(f"- {p.name}: {p.description}" for p in request.params) or "- (none)"
    return (
        f"Name: {request.name}\n"
        f"Description: {request.description}\n"
        f"Params:\n{params}\n"
        f"Script:\n{request.script}"
    )


class ReviewService:
    logger = logging.getLogger(__name__)

    def __init__(self, review_model: BaseChatModel):
        self._structured_model = review_model.with_structured_output(LlmReviewResult)

    async def review(self, request: ReviewRequest) -> ReviewResponse:
        self.logger.debug("Reviewing calculation: name=%s", request.name)
        try:
            outcome: LlmReviewResult = await self._structured_model.ainvoke(
                [
                    SystemMessage(content=REVIEW_SYSTEM_PROMPT),
                    HumanMessage(content=_format_calculation(request)),
                ]
            )
        except Exception as exc:
            raise LlmUnavailableException("LLM review call failed") from exc
        self.logger.debug("Review finished: name=%s verdict=%s", request.name, outcome.verdict)
        return ReviewResponse(
            verdict=outcome.verdict,
            issues=[ReviewIssue(type=issue.type, message=issue.message) for issue in outcome.issues],
            suggested_name=outcome.suggested_name,
            suggested_description=outcome.suggested_description,
            suggested_fixes=outcome.suggested_fixes,
        )
