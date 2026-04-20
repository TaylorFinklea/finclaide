#!/usr/bin/env bash

set -euo pipefail

OPTIONS_FILE="${FINCLAIDE_HOME_ASSISTANT_OPTIONS_PATH:-/data/options.json}"
NGINX_TEMPLATE="/etc/finclaide/nginx.ingress.conf.template"
NGINX_CONFIG="/etc/nginx/conf.d/finclaide.conf"

log() {
  printf '[finclaide-addon] %s\n' "$*"
}

fail() {
  log "$*"
  exit 1
}

read_option() {
  local query="$1"
  if [[ ! -f "$OPTIONS_FILE" ]]; then
    return 0
  fi
  jq -er "${query} // empty" "$OPTIONS_FILE" 2>/dev/null || true
}

read_bool() {
  local query="$1"
  local default_value="$2"
  local value
  value="$(read_option "$query")"
  if [[ -z "$value" ]]; then
    printf '%s\n' "$default_value"
    return 0
  fi
  case "$value" in
    true|True|TRUE|1|yes|on) printf 'true\n' ;;
    *) printf 'false\n' ;;
  esac
}

require_value() {
  local name="$1"
  local value="$2"
  [[ -n "$value" ]] || fail "Missing required add-on option: ${name}"
}

render_nginx_config() {
  local api_mode="$1"
  local api_location

  if [[ "$api_mode" == "enabled" ]]; then
    api_location="$(cat <<'EOF'
location /api/ {
  proxy_pass http://127.0.0.1:8050/api/;
  proxy_http_version 1.1;
  proxy_set_header Host $host;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
  proxy_set_header X-Forwarded-Prefix $http_x_ingress_path;
  proxy_set_header X-Ingress-Path $http_x_ingress_path;
}
EOF
)"
  else
    api_location="$(cat <<'EOF'
location /api/ {
  return 404;
}
EOF
)"
  fi

  API_LOCATION="$api_location" NGINX_TEMPLATE="$NGINX_TEMPLATE" NGINX_CONFIG="$NGINX_CONFIG" python - <<'PY'
from pathlib import Path
import os

template = Path(os.environ["NGINX_TEMPLATE"]).read_text()
rendered = template.replace("__API_LOCATION__", os.environ["API_LOCATION"])
Path(os.environ["NGINX_CONFIG"]).write_text(rendered)
PY
}

if [[ ! -f "$OPTIONS_FILE" ]]; then
  fail "Missing add-on options at ${OPTIONS_FILE}."
fi

export YNAB_ACCESS_TOKEN="$(read_option '.ynab_access_token')"
export YNAB_PLAN_ID="$(read_option '.ynab_plan_id')"
export FINCLAIDE_BUDGET_SOURCE="$(read_option '.budget_source')"
export FINCLAIDE_BUDGET_SHEET_NAME="$(read_option '.budget_sheet_name')"
export FINCLAIDE_SCHEDULED_REFRESH_ENABLED="$(read_bool '.scheduled_refresh_enabled' 'true')"
export FINCLAIDE_SCHEDULED_REFRESH_BOOTSTRAP_ON_START="$(read_bool '.scheduled_refresh_bootstrap_on_start' 'true')"
export FINCLAIDE_SCHEDULED_REFRESH_INTERVAL_MINUTES="$(read_option '.scheduled_refresh_interval_minutes')"
export FINCLAIDE_BUDGET_XLSX_DOWNLOAD_PATH="/data/Budget.google.xlsx"

require_value "ynab_access_token" "${YNAB_ACCESS_TOKEN}"
require_value "ynab_plan_id" "${YNAB_PLAN_ID}"

if [[ -z "${FINCLAIDE_BUDGET_SOURCE}" ]]; then
  export FINCLAIDE_BUDGET_SOURCE="google_sheets"
fi

case "${FINCLAIDE_BUDGET_SOURCE}" in
  local_file)
    local_workbook_file="$(read_option '.local_workbook_file')"
    [[ -n "$local_workbook_file" ]] || local_workbook_file="Budget.xlsx"
    export FINCLAIDE_BUDGET_XLSX="/config/${local_workbook_file}"
    [[ -f "${FINCLAIDE_BUDGET_XLSX}" ]] || fail "Local workbook not found at ${FINCLAIDE_BUDGET_XLSX}."
    ;;
  remote_url)
    export FINCLAIDE_BUDGET_XLSX_URL="$(read_option '.remote_workbook_url')"
    require_value "remote_workbook_url" "${FINCLAIDE_BUDGET_XLSX_URL}"
    ;;
  google_sheets)
    google_service_account_file="$(read_option '.google_service_account_file')"
    [[ -n "$google_service_account_file" ]] || google_service_account_file="google-service-account.json"
    export FINCLAIDE_GOOGLE_SERVICE_ACCOUNT_PATH="/config/${google_service_account_file}"
    export FINCLAIDE_GOOGLE_SHEETS_FILE_ID="$(read_option '.google_file_id')"
    require_value "google_file_id" "${FINCLAIDE_GOOGLE_SHEETS_FILE_ID}"
    [[ -f "${FINCLAIDE_GOOGLE_SERVICE_ACCOUNT_PATH}" ]] || fail "Google service account JSON not found at ${FINCLAIDE_GOOGLE_SERVICE_ACCOUNT_PATH}."
    ;;
  *)
    fail "Unsupported budget_source: ${FINCLAIDE_BUDGET_SOURCE}"
    ;;
esac

enable_private_api="$(read_bool '.enable_private_api' 'false')"
api_token="$(read_option '.api_token')"
if [[ "$enable_private_api" == "true" ]]; then
  require_value "api_token" "$api_token"
  export FINCLAIDE_API_TOKEN="$api_token"
  render_nginx_config "enabled"
else
  export FINCLAIDE_API_TOKEN="${api_token:-$(cat /proc/sys/kernel/random/uuid)}"
  render_nginx_config "disabled"
fi

if [[ -z "${FINCLAIDE_BUDGET_SHEET_NAME}" ]]; then
  export FINCLAIDE_BUDGET_SHEET_NAME="2026 Budget"
fi

if [[ -z "${FINCLAIDE_SCHEDULED_REFRESH_INTERVAL_MINUTES}" ]]; then
  export FINCLAIDE_SCHEDULED_REFRESH_INTERVAL_MINUTES="360"
fi

log "Starting Finclaide with budget source ${FINCLAIDE_BUDGET_SOURCE}."

# SvelteKit Node server (adapter-node output). Flask reverse-proxies non-API
# paths to this internal port via FINCLAIDE_FRONTEND_URL.
PORT="${NODE_PORT:-3000}" HOST="${NODE_HOST:-127.0.0.1}" \
  ORIGIN="${FINCLAIDE_PUBLIC_ORIGIN:-http://127.0.0.1:8099}" \
  node /opt/finclaide/frontend/build &
web_pid=$!

gunicorn --bind 127.0.0.1:8050 finclaide.wsgi:server &
app_pid=$!

cleanup() {
  for pid in "$app_pid" "$web_pid"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid"
      wait "$pid" || true
    fi
  done
}

trap cleanup EXIT INT TERM

nginx -g 'daemon off;'
