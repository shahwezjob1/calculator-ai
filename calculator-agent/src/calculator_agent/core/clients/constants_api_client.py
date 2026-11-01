import logging

import httpx

from calculator_agent.core.clients.errors import UpstreamServiceError, raise_for_response


class ConstantsApiClient:
    logger = logging.getLogger(__name__)

    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def upsert(self, name: str, value: float) -> dict:
        response = await self._request("PUT", f"/api/v1/constants/{name}", json={"value": value})
        raise_for_response(response, f"Upserting constant '{name}'")
        return response.json()

    async def delete(self, name: str) -> bool:
        response = await self._request("DELETE", f"/api/v1/constants/{name}")
        if response.status_code == 404:
            return False
        raise_for_response(response, f"Deleting constant '{name}'")
        return True

    async def bulk_search(self, queries: list[str], size: int = 5) -> list[dict]:
        response = await self._request("POST", "/api/v1/constants/search",
                                       json={"queries": queries, "size": size})
        raise_for_response(response, "Searching constants")
        return response.json()["results"]

    async def values_map(self) -> dict[str, float]:
        response = await self._request("GET", "/api/v1/constants/values")
        raise_for_response(response, "Fetching constant values")
        return response.json()

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            return await self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(f"calculator-service is unreachable: {type(exc).__name__}") from exc
