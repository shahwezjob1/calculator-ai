# Pinned base image. Inside the Equinix network, use the approved InfoSec base
# image; for public release this stays the official pinned tag.
FROM python:3.12.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY src ./src

RUN uv pip install --system --no-cache .

EXPOSE 8002

CMD ["uvicorn", "calculator_reviewer.main:app", "--host", "0.0.0.0", "--port", "8002"]
