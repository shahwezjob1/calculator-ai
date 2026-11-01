import logging
import math

from calculator_service.core.clients.reviewer_api_client import ReviewerApiClient
from calculator_service.core.constants import (
    CALCULATION_DISABLED_ERROR_CODE,
    CALCULATION_EXISTS_ERROR_CODE,
    CALCULATION_NOT_FOUND_ERROR_CODE,
    INVALID_PARAMS_ERROR_CODE,
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_FLAGGED,
)
from calculator_service.core.entities.custom_calculation import CustomCalculation
from calculator_service.core.exceptions.bad_request_exception import BadRequestException
from calculator_service.core.exceptions.conflict_exception import ConflictException
from calculator_service.core.exceptions.not_found_exception import NotFoundException
from calculator_service.core.repo.calculation_repository import CalculationRepository
from calculator_service.modules.calculations.dto.calculation_requests import (
    CreateCalculationRequest,
    UpdateCalculationRequest,
)
from calculator_service.modules.calculations.sandbox.script_executor import ScriptExecutor
from calculator_service.modules.calculations.sandbox.script_validator import validate_script
from calculator_service.modules.constants.service.constant_service import validate_identifier


class CalculationService:
    logger = logging.getLogger(__name__)

    def __init__(self, calculation_repository: CalculationRepository,
                 reviewer_client: ReviewerApiClient, script_executor: ScriptExecutor):
        self._calculation_repository = calculation_repository
        self._reviewer_client = reviewer_client
        self._script_executor = script_executor

    def _validate_definition(self, name: str, params: list[dict]) -> None:
        validate_identifier(name)
        param_names = [p["name"] for p in params]
        if len(set(param_names)) != len(param_names):
            raise BadRequestException(INVALID_PARAMS_ERROR_CODE, "Param names must be unique")
        for param_name in param_names:
            validate_identifier(param_name, INVALID_PARAMS_ERROR_CODE)

    async def _review(self, name: str, description: str, script: str, params: list[dict]) -> tuple[str, dict]:
        review = await self._reviewer_client.review(name, description, script, params)
        status = REVIEW_STATUS_APPROVED if review.get("verdict") == "SAFE" else REVIEW_STATUS_FLAGGED
        return status, review

    async def create(self, request: CreateCalculationRequest) -> CustomCalculation:
        params = [p.model_dump() for p in request.params]
        self._validate_definition(request.name, params)
        validate_script(request.script, [p["name"] for p in params])
        status, review = await self._review(request.name, request.description, request.script, params)
        self.logger.debug("Creating calculation: name=%s review_status=%s", request.name, status)
        created = await self._calculation_repository.create(
            request.name, request.description, request.script, params, status, review
        )
        if created is None:
            raise ConflictException(CALCULATION_EXISTS_ERROR_CODE, f"Calculation '{request.name}' already exists")
        return created

    async def update(self, name: str, request: UpdateCalculationRequest) -> CustomCalculation:
        existing = await self._find_or_raise(name)
        new_name = request.name if request.name is not None else existing.name
        description = request.description if request.description is not None else existing.description
        script = request.script if request.script is not None else existing.script
        params = [p.model_dump() for p in request.params] if request.params is not None else existing.params

        name_changed = new_name != existing.name
        script_changed = script != existing.script
        params_changed = params != existing.params
        description_changed = description != existing.description
        if not (name_changed or script_changed or params_changed or description_changed):
            # No-op PATCH: the stored review still covers this exact content.
            return existing

        self._validate_definition(new_name, params)
        if name_changed and await self._calculation_repository.find_by_name(new_name) is not None:
            raise ConflictException(
                CALCULATION_EXISTS_ERROR_CODE, f"Calculation '{new_name}' already exists"
            )
        if script_changed or params_changed:
            # Static validation's only inputs are the script and the param names.
            validate_script(script, [p["name"] for p in params])
        # Any effective change voids the stored verdict: the review is a cross-field
        # consistency check (a rename or description edit can contradict an unchanged script).
        status, review = await self._review(new_name, description, script, params)
        self.logger.debug("Updating calculation: name=%s new_name=%s review_status=%s", name, new_name, status)
        updated = await self._calculation_repository.update(
            name, new_name, description, script, params, status, review
        )
        if updated is None:
            raise NotFoundException(CALCULATION_NOT_FOUND_ERROR_CODE, f"Calculation '{name}' not found")
        return updated

    async def delete(self, name: str) -> None:
        if not await self._calculation_repository.delete(name):
            raise NotFoundException(CALCULATION_NOT_FOUND_ERROR_CODE, f"Calculation '{name}' not found")

    async def get(self, name: str) -> CustomCalculation:
        return await self._find_or_raise(name)

    async def bulk_search(self, queries: list[str], size: int) -> list[tuple[str, list[dict], int]]:
        return await self._calculation_repository.bulk_search(queries, size)

    async def execute(self, name: str, provided_params: dict[str, float]) -> tuple[dict[str, float], float]:
        calculation = await self._find_or_raise(name)
        if calculation.review_status != REVIEW_STATUS_APPROVED:
            raise ConflictException(
                CALCULATION_DISABLED_ERROR_CODE,
                f"Calculation '{name}' is disabled by review and cannot be executed",
                "Edit the calculation to re-run review, or delete it",
            )
        declared = {p["name"] for p in calculation.params}
        provided = set(provided_params)
        if declared != provided:
            missing = sorted(declared - provided)
            unexpected = sorted(provided - declared)
            raise BadRequestException(
                INVALID_PARAMS_ERROR_CODE,
                "Provided params do not match the calculation's declared params",
                f"missing: {missing}, unexpected: {unexpected}",
            )
        for key, value in provided_params.items():
            if not math.isfinite(value):
                raise BadRequestException(INVALID_PARAMS_ERROR_CODE, f"Param '{key}' must be a finite number")
        self.logger.debug("Executing calculation: name=%s", name)
        return await self._script_executor.execute(calculation.script, provided_params)

    async def _find_or_raise(self, name: str) -> CustomCalculation:
        calculation = await self._calculation_repository.find_by_name(name)
        if calculation is None:
            raise NotFoundException(CALCULATION_NOT_FOUND_ERROR_CODE, f"Calculation '{name}' not found")
        return calculation
