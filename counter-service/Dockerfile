FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY counter-service/pyproject.toml counter-service/uv.lock ./
COPY counter-service/main.py .
COPY ./homework2/ .

RUN uv sync --frozen
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]