# Pinned base image. Inside the Equinix network, use the approved InfoSec base
# image; for public release this stays the official pinned tag.
FROM python:3.12.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY src ./src
COPY migrations ./migrations
COPY startup.sh ./

RUN uv pip install --system --no-cache . && chmod +x startup.sh

EXPOSE 8000

CMD ["./startup.sh"]
