ARG FINCLAIDE_REPO_URL=https://github.com/TaylorFinklea/finclaide.git
ARG FINCLAIDE_REF=main

FROM node:22-slim AS frontend-builder
ARG FINCLAIDE_REPO_URL
ARG FINCLAIDE_REF

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${FINCLAIDE_REF}" "${FINCLAIDE_REPO_URL}" /src/finclaide

WORKDIR /src/finclaide/frontend
RUN npm ci
RUN npm run build

FROM python:3.12-slim
ARG FINCLAIDE_REPO_URL
ARG FINCLAIDE_REF

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FINCLAIDE_FRONTEND_DIST=/opt/finclaide/frontend/dist \
    FINCLAIDE_HOME_ASSISTANT_OPTIONS_PATH=/data/options.json \
    FINCLAIDE_DB_PATH=/data/finclaide.db \
    FINCLAIDE_HOST=127.0.0.1 \
    FINCLAIDE_PORT=8050

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl git jq nginx \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${FINCLAIDE_REF}" "${FINCLAIDE_REPO_URL}" /opt/finclaide

WORKDIR /opt/finclaide

COPY --from=frontend-builder /src/finclaide/frontend/dist /opt/finclaide/frontend/dist
COPY run.sh /run.sh
COPY nginx.ingress.conf.template /etc/finclaide/nginx.ingress.conf.template

RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && chmod +x /run.sh \
    && mkdir -p /config /data /etc/finclaide \
    && rm -f /etc/nginx/conf.d/default.conf

EXPOSE 8099

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://127.0.0.1:8099/healthz >/dev/null || exit 1

CMD ["/run.sh"]
