FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY pyproject.toml README.md LICENSE /app/
COPY src /app/src
COPY tests /app/tests

RUN python -m pip install --upgrade pip && \
    python -m pip install ".[dev]"

RUN mkdir -p /data /input && chown -R appuser:appuser /app /data /input

USER appuser

EXPOSE 8050

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8050/healthz', timeout=3).read()"

CMD ["gunicorn", "--bind", "0.0.0.0:8050", "finclaide.wsgi:server"]
