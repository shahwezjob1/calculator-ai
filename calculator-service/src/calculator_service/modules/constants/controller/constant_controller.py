import logging

from fastapi import APIRouter, Depends

from calculator_service.core.dependencies import get_constant_service
from calculator_service.modules.constants.dto.bulk_search import (
    BulkSearchRequest,
    BulkSearchResponse,
    ConstantSearchResult,
)
from calculator_service.modules.constants.dto.constant_requests import UpsertConstantRequest
from calculator_service.modules.constants.dto.constant_response import ConstantResponse
from calculator_service.modules.constants.service.constant_service import ConstantService

router = APIRouter(prefix="/constants", tags=["Constants"])
logger = logging.getLogger(__name__)


# Constants are a key-value resource: PUT is the single write verb (upsert),
# following the KV precedent (S3 / Consul / etcd). No POST/PATCH.
@router.put("/{name}", response_model=ConstantResponse)
async def upsert_constant(
    name: str,
    request: UpsertConstantRequest,
    constant_service: ConstantService = Depends(get_constant_service),
):
    logger.info("Controller request started: upsert_constant name=%s", name)
    return ConstantResponse.from_entity(await constant_service.upsert(name, request.value))


@router.delete("/{name}", status_code=204)
async def delete_constant(
    name: str,
    constant_service: ConstantService = Depends(get_constant_service),
):
    logger.info("Controller request started: delete_constant name=%s", name)
    await constant_service.delete(name)


@router.post("/search", response_model=BulkSearchResponse)
async def search_constants(
    request: BulkSearchRequest,
    constant_service: ConstantService = Depends(get_constant_service),
):
    logger.info("Controller request started: search_constants queries=%s", len(request.queries))
    results = await constant_service.bulk_search(request.queries, request.size)
    return BulkSearchResponse(
        results=[ConstantSearchResult(query=q, matches=m, total=t) for q, m, t in results]
    )


@router.get("/values", response_model=dict[str, float])
async def get_constant_values(
    constant_service: ConstantService = Depends(get_constant_service),
):
    logger.info("Controller request started: get_constant_values")
    return await constant_service.values_map()
