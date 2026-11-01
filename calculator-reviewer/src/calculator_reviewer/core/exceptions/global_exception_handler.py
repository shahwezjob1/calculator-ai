import logging

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from calculator_reviewer.core.constants import (
    GENERIC_ERROR_MESSAGE,
    INTERNAL_ERROR_CODE,
    VALIDATION_FAILED_ERROR_CODE,
    VALIDATION_FAILED_MESSAGE,
)
from calculator_reviewer.core.dto.error import Error
from calculator_reviewer.core.dto.errors import Errors
from calculator_reviewer.core.dto.info import Info
from calculator_reviewer.core.exceptions.llm_unavailable_exception import LlmUnavailableException
from calculator_reviewer.core.exceptions.reviewer_exception import ReviewerException

logger = logging.getLogger(__name__)


def _build_errors(error_code: str, error_message: str, details: str | None = None,
                  additional_info: list[Info] | None = None) -> dict:
    return Errors(
        errors=[
            Error(
                error_code=error_code,
                error_message=error_message,
                details=details,
                additional_info=additional_info or [],
            )
        ]
    ).model_dump(by_alias=True)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(LlmUnavailableException)
    async def llm_unavailable_handler(request, exc: LlmUnavailableException):
        logger.warning("Request failed with LlmUnavailableException: %s", exc.message)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_build_errors(exc.error_code, exc.message, exc.details),
        )

    @app.exception_handler(ReviewerException)
    async def reviewer_exception_handler(request, exc: ReviewerException):
        logger.error("Request failed with ReviewerException: %s", exc.message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_build_errors(exc.error_code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc: RequestValidationError):
        additional_info = [
            Info(property=str(error["loc"][-1]), reason=error["msg"]) for error in exc.errors()
        ]
        logger.warning("Request validation failed: %s", [i.model_dump() for i in additional_info])
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_build_errors(
                VALIDATION_FAILED_ERROR_CODE, VALIDATION_FAILED_MESSAGE, additional_info=additional_info
            ),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request, exc: Exception):
        logger.exception("Unhandled exception")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_build_errors(INTERNAL_ERROR_CODE, GENERIC_ERROR_MESSAGE),
        )
