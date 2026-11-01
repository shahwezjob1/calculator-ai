#!/usr/bin/env bash
set -e

python -m calculator_service.core.migrations
exec uvicorn calculator_service.main:app --host 0.0.0.0 --reload --port "${SERVER_PORT:-8001}"
