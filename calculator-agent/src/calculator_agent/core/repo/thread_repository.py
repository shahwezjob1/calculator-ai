from uuid import UUID

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from calculator_agent.core.entities.thread import Thread


def _to_entity(row: dict) -> Thread:
    return Thread(**row)


class ThreadRepository:
    def __init__(self, pool: AsyncConnectionPool):
        self._pool = pool

    async def create(self, thread_id: UUID, thread_name: str) -> Thread:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "INSERT INTO threads (thread_id, thread_name) VALUES (%s, %s) RETURNING *",
                    (thread_id, thread_name),
                )
                row = await cur.fetchone()
        return _to_entity(row)

    async def exists(self, thread_id: UUID) -> bool:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1 FROM threads WHERE thread_id = %s", (thread_id,))
                return await cur.fetchone() is not None

    async def find_all(self, page: int, size: int) -> tuple[list[Thread], int]:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT COUNT(*) AS total FROM threads")
                total = (await cur.fetchone())["total"]
                await cur.execute(
                    "SELECT * FROM threads ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (size, (page - 1) * size),
                )
                rows = await cur.fetchall()
        return [_to_entity(row) for row in rows], total

    async def delete(self, thread_id: UUID) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM threads WHERE thread_id = %s",
                    (thread_id,),
                )

    async def update_title(self, thread_id: UUID, title: str) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE threads
                    SET thread_name = %s
                    WHERE thread_id = %s
                    """,
                    (title, thread_id),
                )