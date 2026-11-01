from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from calculator_service.core.entities.custom_calculation import CustomCalculation


def _to_entity(row: dict) -> CustomCalculation:
    return CustomCalculation(**row)


class CalculationRepository:
    def __init__(self, pool: AsyncConnectionPool):
        self._pool = pool

    async def create(self, name: str, description: str, script: str, params: list[dict],
                     review_status: str, review_notes: dict | None) -> CustomCalculation | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "INSERT INTO custom_calculations "
                    "(name, description, script, params, review_status, review_notes) "
                    "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (name) DO NOTHING RETURNING *",
                    (name, description, script, Jsonb(params), review_status,
                     Jsonb(review_notes) if review_notes is not None else None),
                )
                row = await cur.fetchone()
        return _to_entity(row) if row else None

    async def update(self, name: str, new_name: str, description: str, script: str, params: list[dict],
                     review_status: str, review_notes: dict | None) -> CustomCalculation | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "UPDATE custom_calculations SET name = %s, description = %s, script = %s, "
                    "params = %s, review_status = %s, review_notes = %s, updated_at = CURRENT_TIMESTAMP "
                    "WHERE name = %s RETURNING *",
                    (new_name, description, script, Jsonb(params), review_status,
                     Jsonb(review_notes) if review_notes is not None else None, name),
                )
                row = await cur.fetchone()
        return _to_entity(row) if row else None

    async def delete(self, name: str) -> bool:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM custom_calculations WHERE name = %s", (name,))
                return cur.rowcount > 0

    async def find_by_name(self, name: str) -> CustomCalculation | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM custom_calculations WHERE name = %s", (name,))
                row = await cur.fetchone()
        return _to_entity(row) if row else None

    async def bulk_search(self, queries: list[str], size: int) -> list[tuple[str, list[dict], int]]:
        results: list[tuple[str, list[dict], int]] = []
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                for query in queries:
                    pattern = "%" if query in ("", "*") else f"%{query}%"
                    await cur.execute(
                        "SELECT COUNT(*) AS total FROM custom_calculations "
                        "WHERE name ILIKE %s OR description ILIKE %s",
                        (pattern, pattern),
                    )
                    total = (await cur.fetchone())["total"]
                    await cur.execute(
                        "SELECT name, description FROM custom_calculations "
                        "WHERE name ILIKE %s OR description ILIKE %s ORDER BY name LIMIT %s",
                        (pattern, pattern, size),
                    )
                    matches = await cur.fetchall()
                    results.append((query, matches, total))
        return results
