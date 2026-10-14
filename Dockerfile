# Samjho API image (the backend/ folder): FastAPI + LangGraph + SymPy. Tables and the question bank are set up on
# start. It lives at the repo root so Render's default Dockerfile path works; build context is the repo root.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/app ./app
RUN useradd --create-home samjho && mkdir -p storage && chown -R samjho:samjho /app
USER samjho

EXPOSE 8000
CMD ["sh", "-c", "uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
