from functools import lru_cache

from fastapi import Depends

from calculator_reviewer.core.llm.factory import build_review_model
from calculator_reviewer.modules.review.service.author_service import AuthorService
from calculator_reviewer.modules.review.service.generate_service import GenerateService
from calculator_reviewer.modules.review.service.review_service import ReviewService


@lru_cache
def get_review_model():
    return build_review_model()


def get_review_service(review_model=Depends(get_review_model)) -> ReviewService:
    return ReviewService(review_model)


def get_generate_service(review_model=Depends(get_review_model)) -> GenerateService:
    return GenerateService(review_model)


def get_author_service(
    generate_service: GenerateService = Depends(get_generate_service),
    review_service: ReviewService = Depends(get_review_service),
) -> AuthorService:
    return AuthorService(generate_service=generate_service, review_service=review_service)
