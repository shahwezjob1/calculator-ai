from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from calculator_service.core.entities.custom_constant import CustomConstant


def _to_entity(row: dict) -> CustomConstant:
    return CustomConstant(**row)


class ConstantRepository:
    def __init__(self, pool: AsyncConnectionPool):
        self._pool = pool

    async def upsert(self, name: str, value: float) -> CustomConstant:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "INSERT INTO custom_constants (name, value) VALUES (%s, %s) "
                    "ON CONFLICT (name) DO UPDATE SET value = EXCLUDED.value, "
                    "updated_at = CURRENT_TIMESTAMP RETURNING *",
                    (name, value),
                )
                row = await cur.fetchone()
        return _to_entity(row)

    async def delete(self, name: str) -> bool:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM custom_constants WHERE name = %s", (name,))
                return cur.rowcount > 0

    async def bulk_search(self, queries: list[str], size: int) -> list[tuple[str, list[str], int]]:
        results: list[tuple[str, list[str], int]] = []
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                for query in queries:
                    pattern = "%" if query in ("", "*") else f"%{query}%"
                    await cur.execute(
                        "SELECT COUNT(*) AS total FROM custom_constants WHERE name ILIKE %s", (pattern,)
                    )
                    total = (await cur.fetchone())["total"]
                    await cur.execute(
                        "SELECT name FROM custom_constants WHERE name ILIKE %s ORDER BY name LIMIT %s",
                        (pattern, size),
                    )
                    names = [row["name"] for row in await cur.fetchall()]
                    results.append((query, names, total))
        return results

    async def as_values_map(self) -> dict[str, float]:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT name, value FROM custom_constants")
                rows = await cur.fetchall()
        return {row["name"]: row["value"] for row in rows}
