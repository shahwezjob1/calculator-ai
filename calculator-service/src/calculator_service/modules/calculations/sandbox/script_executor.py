import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from calculator_service.core.config import settings
from calculator_service.core.constants import (
    EXECUTION_FAILED_ERROR_CODE,
    EXECUTION_TIMEOUT_ERROR_CODE,
)
from calculator_service.core.exceptions.unprocessable_exception import UnprocessableException

RUNNER_PATH = Path(__file__).resolve().parent / "runner.py"


class ScriptExecutor:
    logger = logging.getLogger(__name__)

    async def execute(self, script: str, params: dict[str, float]) -> tuple[dict[str, float], float]:
        payload = json.dumps(
            {
                "script": script,
                "params": params,
                "limits": {
                    "cpu_seconds": settings.exec_timeout_seconds,
                    "memory_mb": settings.exec_memory_limit_mb,
                },
            }
        ).encode()
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-I", str(RUNNER_PATH),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        started = time.perf_counter()
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(payload), timeout=settings.exec_timeout_seconds
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            raise UnprocessableException(
                EXECUTION_TIMEOUT_ERROR_CODE,
                f"Script execution exceeded {settings.exec_timeout_seconds}s and was terminated",
            )
        duration_ms = (time.perf_counter() - started) * 1000
        if process.returncode != 0:
            self.logger.warning("Script process exited with code %s", process.returncode)
            raise UnprocessableException(
                EXECUTION_FAILED_ERROR_CODE,
                "Script execution process failed",
                stderr.decode(errors="replace")[:200] or None,
            )
        try:
            outcome = json.loads(stdout)
        except json.JSONDecodeError:
            raise UnprocessableException(EXECUTION_FAILED_ERROR_CODE, "Script produced unreadable output")
        if not outcome.get("ok"):
            raise UnprocessableException(EXECUTION_FAILED_ERROR_CODE, outcome.get("error", "Script failed"))
        return outcome["result"], duration_ms
