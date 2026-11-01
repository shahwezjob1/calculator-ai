from fastapi import Depends, Request

from calculator_service.core.clients.reviewer_api_client import ReviewerApiClient
from calculator_service.core.repo.calculation_repository import CalculationRepository
from calculator_service.core.repo.constant_repository import ConstantRepository
from calculator_service.modules.calculations.sandbox.script_executor import ScriptExecutor
from calculator_service.modules.calculations.service.calculation_service import CalculationService
from calculator_service.modules.constants.service.constant_service import ConstantService


def get_pool(request: Request):
    return request.app.state.pool


def get_reviewer_client(request: Request) -> ReviewerApiClient:
    return request.app.state.reviewer_client


def get_constant_repository(pool=Depends(get_pool)) -> ConstantRepository:
    return ConstantRepository(pool)


def get_calculation_repository(pool=Depends(get_pool)) -> CalculationRepository:
    return CalculationRepository(pool)


def get_script_executor() -> ScriptExecutor:
    return ScriptExecutor()


def get_constant_service(
    constant_repository: ConstantRepository = Depends(get_constant_repository),
) -> ConstantService:
    return ConstantService(constant_repository=constant_repository)


def get_calculation_service(
    calculation_repository: CalculationRepository = Depends(get_calculation_repository),
    reviewer_client: ReviewerApiClient = Depends(get_reviewer_client),
    script_executor: ScriptExecutor = Depends(get_script_executor),
) -> CalculationService:
    return CalculationService(
        calculation_repository=calculation_repository,
        reviewer_client=reviewer_client,
        script_executor=script_executor,
    )
