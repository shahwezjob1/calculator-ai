#!/usr/bin/env bash
set -e

python -m calculator_agent.core.migrations
exec uvicorn calculator_agent.main:app --host 0.0.0.0 --reload --port "${SERVER_PORT:-8000}"
