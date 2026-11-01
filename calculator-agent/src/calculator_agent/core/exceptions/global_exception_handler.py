import logging

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from calculator_agent.core.constants import (
    GENERIC_ERROR_MESSAGE,
    INTERNAL_ERROR_CODE,
    VALIDATION_FAILED_ERROR_CODE,
    VALIDATION_FAILED_MESSAGE,
)
from calculator_agent.core.dto.error import Error
from calculator_agent.core.dto.errors import Errors
from calculator_agent.core.dto.info import Info
from calculator_agent.core.exceptions.calculator_agent_exception import CalculatorAgentException
from calculator_agent.core.exceptions.conflict_exception import ConflictException
from calculator_agent.core.exceptions.not_found_exception import NotFoundException

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
    @app.exception_handler(NotFoundException)
    async def not_found_handler(request, exc: NotFoundException):
        logger.warning("Request failed (%s): %s", exc.error_code, exc.message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND,
                            content=_build_errors(exc.error_code, exc.message, exc.details))

    @app.exception_handler(ConflictException)
    async def conflict_handler(request, exc: ConflictException):
        logger.warning("Request failed (%s): %s", exc.error_code, exc.message)
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content=_build_errors(exc.error_code, exc.message, exc.details))

    @app.exception_handler(CalculatorAgentException)
    async def base_handler(request, exc: CalculatorAgentException):
        logger.error("Request failed (%s): %s", exc.error_code, exc.message)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            content=_build_errors(exc.error_code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, exc: RequestValidationError):
        additional_info = [Info(property=str(e["loc"][-1]), reason=e["msg"]) for e in exc.errors()]
        logger.warning("Request validation failed: %s", [i.model_dump() for i in additional_info])
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_build_errors(VALIDATION_FAILED_ERROR_CODE, VALIDATION_FAILED_MESSAGE,
                                  additional_info=additional_info),
        )

    @app.exception_handler(Exception)
    async def generic_handler(request, exc: Exception):
        logger.exception("Unhandled exception")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            content=_build_errors(INTERNAL_ERROR_CODE, GENERIC_ERROR_MESSAGE))
