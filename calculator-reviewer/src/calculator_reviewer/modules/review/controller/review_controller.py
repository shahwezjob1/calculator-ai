import logging

from fastapi import APIRouter, Depends

from calculator_reviewer.core.dependencies import (
    get_author_service,
    get_generate_service,
    get_review_service,
)
from calculator_reviewer.modules.review.dto.author_request import AuthorRequest
from calculator_reviewer.modules.review.dto.author_response import AuthorResponse
from calculator_reviewer.modules.review.dto.generate_request import GenerateRequest
from calculator_reviewer.modules.review.dto.generate_response import GenerateResponse
from calculator_reviewer.modules.review.dto.review_request import ReviewRequest
from calculator_reviewer.modules.review.dto.review_response import ReviewResponse
from calculator_reviewer.modules.review.service.author_service import AuthorService
from calculator_reviewer.modules.review.service.generate_service import GenerateService
from calculator_reviewer.modules.review.service.review_service import ReviewService

router = APIRouter(tags=["Review"])
logger = logging.getLogger(__name__)


@router.post("/review", response_model=ReviewResponse)
async def review_calculation(
    request: ReviewRequest,
    review_service: ReviewService = Depends(get_review_service),
):
    logger.info("Controller request started: review_calculation name=%s", request.name)
    response = await review_service.review(request)
    logger.info("Controller response ready: review_calculation name=%s verdict=%s", request.name, response.verdict)
    return response


@router.post("/generate", response_model=GenerateResponse)
async def generate_calculation(
    request: GenerateRequest,
    generate_service: GenerateService = Depends(get_generate_service),
):
    logger.info("Controller request started: generate_calculation name=%s", request.name)
    response = await generate_service.generate(request)
    logger.info("Controller response ready: generate_calculation name=%s", response.name)
    return response


@router.post("/author", response_model=AuthorResponse)
async def author_calculation(
    request: AuthorRequest,
    author_service: AuthorService = Depends(get_author_service),
):
    logger.info("Controller request started: author_calculation name=%s", request.name)
    response = await author_service.author(request)
    logger.info(
        "Controller response ready: author_calculation name=%s iterations=%s verdict=%s",
        response.name, response.iterations, response.review.verdict,
    )
    return response
