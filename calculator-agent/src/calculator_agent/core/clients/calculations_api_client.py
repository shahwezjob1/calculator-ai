import logging

import httpx

from calculator_agent.core.clients.errors import UpstreamServiceError, raise_for_response


class CalculationsApiClient:
    logger = logging.getLogger(__name__)

    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def create(self, name: str, description: str, script: str, params: list[dict]) -> dict:
        response = await self._request(
            "POST", "/api/v1/calculations",
            json={"name": name, "description": description, "script": script, "params": params},
        )
        raise_for_response(response, f"Creating calculation '{name}'")
        return response.json()

    async def update(self, original_name: str, payload: dict) -> dict:
        response = await self._request("PATCH", f"/api/v1/calculations/{original_name}", json=payload)
        raise_for_response(response, f"Updating calculation '{original_name}'")
        return response.json()

    async def delete(self, name: str) -> bool:
        response = await self._request("DELETE", f"/api/v1/calculations/{name}")
        if response.status_code == 404:
            return False
        raise_for_response(response, f"Deleting calculation '{name}'")
        return True

    async def get(self, name: str) -> dict:
        response = await self._request("GET", f"/api/v1/calculations/{name}")
        raise_for_response(response, f"Fetching calculation '{name}'")
        return response.json()

    async def bulk_search(self, queries: list[str], size: int = 5) -> list[dict]:
        response = await self._request("POST", "/api/v1/calculations/search",
                                       json={"queries": queries, "size": size})
        raise_for_response(response, "Searching calculations")
        return response.json()["results"]

    async def execute(self, name: str, params: dict[str, float]) -> dict:
        response = await self._request("POST", f"/api/v1/calculations/{name}/execute",
                                       json={"params": params})
        raise_for_response(response, f"Executing calculation '{name}'")
        return response.json()

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            return await self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(f"calculator-service is unreachable: {type(exc).__name__}") from exc
