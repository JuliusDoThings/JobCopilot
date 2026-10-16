FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.0 \
    && useradd --create-home --uid 10001 app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable
USER app
EXPOSE 8000
CMD [".venv/bin/uvicorn", "job_copilot_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
