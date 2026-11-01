import asyncio
import logging
import os
import re
from pathlib import Path

import psycopg

from calculator_service.core.config import settings

logger = logging.getLogger(__name__)

MIGRATION_FILE_PATTERN = re.compile(r"^V(\d+)__.+\.sql$")


def _collect_migrations(directory: Path) -> list[tuple[int, Path]]:
    if not directory.is_dir():
        raise RuntimeError(f"Migrations directory not found: {directory}")
    collected: list[tuple[int, Path]] = []
    seen: dict[int, Path] = {}
    for path in directory.glob("*.sql"):
        match = MIGRATION_FILE_PATTERN.match(path.name)
        if not match:
            raise RuntimeError(f"Migration filename does not match V<N>__<name>.sql: {path.name}")
        version = int(match.group(1))
        if version in seen:
            raise RuntimeError(f"Duplicate migration version {version}: {path.name} and {seen[version].name}")
        seen[version] = path
        collected.append((version, path))
    # Numeric sort: lexicographic ordering would run V10 before V2 (and before V1).
    return sorted(collected, key=lambda item: item[0])


async def apply_migrations(directory: Path | None = None) -> None:
    directory = directory or Path(os.getenv("MIGRATIONS_DIR", "migrations/versions"))
    migrations = _collect_migrations(directory)
    async with await psycopg.AsyncConnection.connect(settings.database_url, autocommit=True) as conn:
        for version, path in migrations:
            await conn.execute(path.read_text())
            logger.info("Applied migration: %s", path.name)


if __name__ == "__main__":
    from calculator_service.core.logging_config import configure_logging

    configure_logging()
    asyncio.run(apply_migrations())
