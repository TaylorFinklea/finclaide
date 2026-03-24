from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, Response, current_app, jsonify, request

from finclaide.errors import DataIntegrityError
from finclaide.operations import run_budget_import, run_reconcile, run_ynab_sync

ui_api = Blueprint("ui_api", __name__, url_prefix="/ui-api")


def _container():
    return current_app.extensions["finclaide"]


def _request_origin() -> str:
    return request.headers.get("Origin", "").rstrip("/")


def _expected_origin() -> str:
    return request.host_url.rstrip("/")


def require_same_origin(handler: Callable[..., Response]):
    @wraps(handler)
    def wrapped(*args: Any, **kwargs: Any):
        origin = _request_origin()
        if origin and origin != _expected_origin():
            return jsonify({"error": "forbidden"}), 403
        fetch_site = request.headers.get("Sec-Fetch-Site", "")
        if fetch_site and fetch_site not in {"same-origin", "none"}:
            return jsonify({"error": "forbidden"}), 403
        return handler(*args, **kwargs)

    return wrapped


def require_ui_write_request(handler: Callable[..., Response]):
    @wraps(handler)
    @require_same_origin
    def wrapped(*args: Any, **kwargs: Any):
        if not request.is_json:
            return jsonify({"error": "json_required"}), 415
        if request.headers.get("X-Finclaide-UI") != "1":
            return jsonify({"error": "missing_ui_header"}), 403
        return handler(*args, **kwargs)

    return wrapped


@ui_api.get("/status")
@require_same_origin
def status():
    return jsonify(_container().reports.status(include_recent_runs=True))


@ui_api.get("/runs")
@require_same_origin
def runs():
    limit = min(max(int(request.args.get("limit", "20")), 1), 100)
    return jsonify(_container().reports.runs(limit=limit, source=request.args.get("source")))


@ui_api.get("/summary")
@require_same_origin
def summary():
    month = request.args.get("month")
    return jsonify(_container().reports.summary(month=month))


@ui_api.get("/review/weekly")
@require_same_origin
def weekly_review():
    return jsonify(_container().review.weekly(month=request.args.get("month")))


@ui_api.get("/transactions")
@require_same_origin
def transactions():
    limit = min(max(int(request.args.get("limit", "50")), 1), 500)
    offset = max(int(request.args.get("offset", "0")), 0)
    result = _container().reports.transactions_page(
        since=request.args.get("since"),
        until=request.args.get("until"),
        group_name=request.args.get("group"),
        category_name=request.args.get("category"),
        query=request.args.get("q"),
        limit=limit,
        offset=offset,
    )
    return jsonify(result)


@ui_api.post("/operations/import-budget")
@require_ui_write_request
def import_budget():
    container = _container()
    with container.operation_lock.guard("budget_import"):
        result = run_budget_import(container)
    return jsonify(result)


@ui_api.post("/operations/sync-ynab")
@require_ui_write_request
def sync_ynab():
    container = _container()
    with container.operation_lock.guard("ynab_sync"):
        result = run_ynab_sync(container)
    return jsonify(result)


@ui_api.post("/operations/reconcile")
@require_ui_write_request
def reconcile():
    container = _container()
    with container.operation_lock.guard("reconcile"):
        result = run_reconcile(container)
    return jsonify(result)


@ui_api.post("/operations/refresh-all")
@require_ui_write_request
def refresh_all():
    container = _container()
    month = (request.get_json(silent=True) or {}).get("month")
    with container.operation_lock.guard("refresh_all"):
        budget_import = run_budget_import(container)
        ynab_sync = run_ynab_sync(container)
        try:
            reconcile_result = run_reconcile(container)
            status_code = 200
            payload = {"reconcile": reconcile_result}
        except DataIntegrityError as error:
            status_code = 400
            payload = {"reconcile_error": {"kind": "application_error", "message": str(error)}}
        payload.update(
            {
                "budget_import": budget_import,
                "ynab_sync": ynab_sync,
                "status": container.reports.status(include_recent_runs=True),
                "summary": container.reports.summary(month=month),
            }
        )
    return jsonify(payload), status_code
