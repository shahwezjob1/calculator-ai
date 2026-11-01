import logging

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from calculator_service.core.constants import (
    GENERIC_ERROR_MESSAGE,
    INTERNAL_ERROR_CODE,
    VALIDATION_FAILED_ERROR_CODE,
    VALIDATION_FAILED_MESSAGE,
)
from calculator_service.core.dto.error import Error
from calculator_service.core.dto.errors import Errors
from calculator_service.core.dto.info import Info
from calculator_service.core.exceptions.bad_request_exception import BadRequestException
from calculator_service.core.exceptions.calculator_service_exception import CalculatorServiceException
from calculator_service.core.exceptions.conflict_exception import ConflictException
from calculator_service.core.exceptions.not_found_exception import NotFoundException
from calculator_service.core.exceptions.service_unavailable_exception import ServiceUnavailableException
from calculator_service.core.exceptions.unprocessable_exception import UnprocessableException

logger = logging.getLogger(__name__)

_STATUS_BY_EXCEPTION = [
    (BadRequestException, status.HTTP_400_BAD_REQUEST),
    (NotFoundException, status.HTTP_404_NOT_FOUND),
    (ConflictException, status.HTTP_409_CONFLICT),
    (UnprocessableException, 422),
    (ServiceUnavailableException, status.HTTP_503_SERVICE_UNAVAILABLE),
]


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
    def _make_handler(status_code: int):
        async def handler(request, exc: CalculatorServiceException):
            logger.warning("Request failed (%s): %s", exc.error_code, exc.message)
            return JSONResponse(
                status_code=status_code,
                content=_build_errors(exc.error_code, exc.message, exc.details),
            )

        return handler

    for exception_class, status_code in _STATUS_BY_EXCEPTION:
        app.add_exception_handler(exception_class, _make_handler(status_code))

    @app.exception_handler(CalculatorServiceException)
    async def base_exception_handler(request, exc: CalculatorServiceException):
        logger.error("Request failed (%s): %s", exc.error_code, exc.message)
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
