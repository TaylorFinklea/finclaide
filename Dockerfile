FROM node:22-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json /app/frontend/
RUN npm ci
COPY frontend /app/frontend
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FINCLAIDE_FRONTEND_DIST=/app/frontend/dist

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY pyproject.toml README.md LICENSE /app/
COPY src /app/src
COPY tests /app/tests
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

RUN python -m pip install --upgrade pip && \
    python -m pip install ".[dev]"

RUN mkdir -p /data /input && chown -R appuser:appuser /app /data /input

USER appuser

EXPOSE 8050

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8050/healthz', timeout=3).read()"

CMD ["gunicorn", "--bind", "0.0.0.0:8050", "finclaide.wsgi:server"]
