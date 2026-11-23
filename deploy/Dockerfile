# syntax=docker/dockerfile:1

# Stage 1: build the dashboard SPA.
FROM node:22-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN npm install -g pnpm@10 && pnpm install --frozen-lockfile --ignore-scripts
COPY frontend/ ./
RUN pnpm run build

# Stage 2: runtime gateway with the SPA baked in.
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    POLYGATE_STATIC_DIR=/app/frontend/dist
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /usr/local/bin/uv
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --no-dev --no-install-project --frozen
COPY backend/ ./
RUN uv sync --no-dev --frozen
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
RUN useradd --system --no-create-home --uid 10001 polygate && mkdir -p /app/data /home/polygate/.cache \
    && chown -R polygate /app/data /home/polygate
USER polygate
ENV HOME=/home/polygate \
    UV_CACHE_DIR=/home/polygate/.cache/uv \
    POLYGATE_DATABASE=/app/data/polygate.db
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=3)"
CMD ["uv", "run", "--no-dev", "--no-sync", "uvicorn", "polygate.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
