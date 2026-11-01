import logging
import math
import re

from calculator_service.core.constants import (
    CONSTANT_NOT_FOUND_ERROR_CODE,
    INVALID_NAME_ERROR_CODE,
    INVALID_VALUE_ERROR_CODE,
    NAME_PATTERN,
    UNIVERSAL_NAMES,
)
from calculator_service.core.entities.custom_constant import CustomConstant
from calculator_service.core.exceptions.bad_request_exception import BadRequestException
from calculator_service.core.exceptions.not_found_exception import NotFoundException
from calculator_service.core.repo.constant_repository import ConstantRepository


def validate_identifier(name: str, error_code: str = INVALID_NAME_ERROR_CODE) -> None:
    if not re.fullmatch(NAME_PATTERN, name):
        raise BadRequestException(error_code, f"Invalid name '{name}': must match {NAME_PATTERN}")
    if "__" in name:
        raise BadRequestException(error_code, f"Invalid name '{name}': double underscores are not allowed")
    if name in UNIVERSAL_NAMES:
        raise BadRequestException(
            error_code, f"Invalid name '{name}': collides with a built-in function or constant"
        )


class ConstantService:
    logger = logging.getLogger(__name__)

    def __init__(self, constant_repository: ConstantRepository):
        self._constant_repository = constant_repository

    def _validate(self, name: str, value: float) -> None:
        validate_identifier(name)
        if not math.isfinite(value):
            raise BadRequestException(INVALID_VALUE_ERROR_CODE, "Constant value must be a finite number")

    async def upsert(self, name: str, value: float) -> CustomConstant:
        self._validate(name, value)
        return await self._constant_repository.upsert(name, value)

    async def delete(self, name: str) -> None:
        if not await self._constant_repository.delete(name):
            raise NotFoundException(CONSTANT_NOT_FOUND_ERROR_CODE, f"Constant '{name}' not found")

    async def bulk_search(self, queries: list[str], size: int) -> list[tuple[str, list[str], int]]:
        return await self._constant_repository.bulk_search(queries, size)

    async def values_map(self) -> dict[str, float]:
        return await self._constant_repository.as_values_map()
