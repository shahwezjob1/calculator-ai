import logging

from calculator_reviewer.modules.review.dto.author_request import AuthorRequest
from calculator_reviewer.modules.review.dto.author_response import AuthorResponse
from calculator_reviewer.modules.review.dto.generate_request import GenerateRequest
from calculator_reviewer.modules.review.dto.generate_response import GenerateResponse
from calculator_reviewer.modules.review.dto.review_request import ReviewRequest
from calculator_reviewer.modules.review.dto.review_response import ReviewResponse
from calculator_reviewer.modules.review.service.generate_service import GenerateService
from calculator_reviewer.modules.review.service.review_service import ReviewService

# QUALITY findings alone should not force another generation lap.
BLOCKING_ISSUE_TYPES = {"SAFETY", "CORRECTNESS"}


def _is_clean(review: ReviewResponse) -> bool:
    return review.verdict == "SAFE" and not any(i.type in BLOCKING_ISSUE_TYPES for i in review.issues)


def _build_refine_prompt(original_prompt: str, candidate: GenerateResponse, review: ReviewResponse) -> str:
    issues = "\n".join(f"- [{i.type}] {i.message}" for i in review.issues) or "- (none)"
    fixes = "\n".join(f"- {f}" for f in review.suggested_fixes) or "- (none)"
    return (
        f"{original_prompt}\n\n"
        f"A previous attempt was reviewed and needs improvement.\n"
        f"Previous script:\n{candidate.script}\n"
        f"Review issues:\n{issues}\n"
        f"Suggested fixes:\n{fixes}\n"
        f"Produce an improved calculation that addresses these issues."
    )


class AuthorService:
    logger = logging.getLogger(__name__)

    def __init__(self, generate_service: GenerateService, review_service: ReviewService):
        self._generate_service = generate_service
        self._review_service = review_service

    async def author(self, request: AuthorRequest) -> AuthorResponse:
        candidate = await self._generate_service.generate(
            GenerateRequest(prompt=request.prompt, name=request.name, params_hint=request.params_hint)
        )
        iterations = 1
        while True:
            review = await self._review_service.review(
                ReviewRequest(
                    name=candidate.name,
                    description=candidate.description,
                    script=candidate.script,
                    params=candidate.params,
                )
            )
            if _is_clean(review) or iterations >= request.max_iterations:
                break
            self.logger.debug(
                "Authoring iteration %s found blocking issues: name=%s", iterations, candidate.name
            )
            candidate = await self._generate_service.generate(
                GenerateRequest(
                    prompt=_build_refine_prompt(request.prompt, candidate, review),
                    name=candidate.name,
                    params_hint=candidate.params,
                )
            )
            iterations += 1
        self.logger.debug(
            "Authoring finished: name=%s iterations=%s verdict=%s", candidate.name, iterations, review.verdict
        )
        return AuthorResponse(
            name=candidate.name,
            description=candidate.description,
            script=candidate.script,
            params=candidate.params,
            notes=candidate.notes,
            review=review,
            iterations=iterations,
        )
