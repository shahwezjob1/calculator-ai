import logging

from fastapi import APIRouter, Depends

from calculator_service.core.dependencies import get_calculation_service
from calculator_service.modules.calculations.dto.calculation_requests import (
    CreateCalculationRequest,
    ExecuteCalculationRequest,
    UpdateCalculationRequest,
)
from calculator_service.modules.calculations.dto.calculation_response import CalculationResponse
from calculator_service.modules.calculations.dto.calculation_search import (
    CalculationBulkSearchRequest,
    CalculationBulkSearchResponse,
    CalculationSearchResult,
    CalculationSummary,
)
from calculator_service.modules.calculations.dto.execute_response import ExecuteCalculationResponse
from calculator_service.modules.calculations.service.calculation_service import CalculationService

router = APIRouter(prefix="/calculations", tags=["Calculations"])
logger = logging.getLogger(__name__)


@router.post("", response_model=CalculationResponse, status_code=201)
async def create_calculation(
    request: CreateCalculationRequest,
    calculation_service: CalculationService = Depends(get_calculation_service),
):
    logger.info("Controller request started: create_calculation name=%s", request.name)
    response = CalculationResponse.from_entity(await calculation_service.create(request))
    logger.info("Controller response ready: create_calculation name=%s status=%s",
                response.name, response.review_status)
    return response


@router.patch("/{name}", response_model=CalculationResponse)
async def update_calculation(
    name: str,
    request: UpdateCalculationRequest,
    calculation_service: CalculationService = Depends(get_calculation_service),
):
    logger.info("Controller request started: update_calculation name=%s", name)
    response = CalculationResponse.from_entity(await calculation_service.update(name, request))
    logger.info("Controller response ready: update_calculation name=%s status=%s",
                response.name, response.review_status)
    return response


@router.delete("/{name}", status_code=204)
async def delete_calculation(
    name: str,
    calculation_service: CalculationService = Depends(get_calculation_service),
):
    logger.info("Controller request started: delete_calculation name=%s", name)
    await calculation_service.delete(name)


@router.post("/search", response_model=CalculationBulkSearchResponse)
async def search_calculations(
    request: CalculationBulkSearchRequest,
    calculation_service: CalculationService = Depends(get_calculation_service),
):
    logger.info("Controller request started: search_calculations queries=%s", len(request.queries))
    results = await calculation_service.bulk_search(request.queries, request.size)
    return CalculationBulkSearchResponse(
        results=[
            CalculationSearchResult(
                query=query,
                matches=[CalculationSummary(**match) for match in matches],
                total=total,
            )
            for query, matches, total in results
        ]
    )


@router.get("/{name}", response_model=CalculationResponse)
async def get_calculation(
    name: str,
    calculation_service: CalculationService = Depends(get_calculation_service),
):
    logger.info("Controller request started: get_calculation name=%s", name)
    return CalculationResponse.from_entity(await calculation_service.get(name))


@router.post("/{name}/execute", response_model=ExecuteCalculationResponse)
async def execute_calculation(
    name: str,
    request: ExecuteCalculationRequest,
    calculation_service: CalculationService = Depends(get_calculation_service),
):
    logger.info("Controller request started: execute_calculation name=%s", name)
    results, duration_ms = await calculation_service.execute(name, request.params)
    logger.info("Controller response ready: execute_calculation name=%s duration_ms=%.2f", name, duration_ms)
    return ExecuteCalculationResponse(results=results, duration_ms=duration_ms)
