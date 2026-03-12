from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, Response, current_app, jsonify, request

from finclaide.errors import ConfigError, DataIntegrityError, FinclaideError, OperationInProgressError

api = Blueprint("api", __name__, url_prefix="/api")


def _container():
    return current_app.extensions["finclaide"]


def require_bearer_token(handler: Callable[..., Response]):
    @wraps(handler)
    def wrapped(*args: Any, **kwargs: Any):
        config = current_app.config["FINCLAIDE_CONFIG"]
        if not config.api_token:
            raise ConfigError("FINCLAIDE_API_TOKEN must be configured before using the API.")
        header_value = request.headers.get("Authorization", "")
        expected = f"Bearer {config.api_token}"
        if header_value != expected:
            return jsonify({"error": "unauthorized"}), 401
        return handler(*args, **kwargs)

    return wrapped


@api.get("/status")
@require_bearer_token
def status():
    return jsonify(_container().reports.status())


@api.post("/budget/import")
@require_bearer_token
def import_budget():
    container = _container()
    with container.operation_lock.guard("budget_import"):
        result = container.budget_importer.import_budget(
            container.config.budget_xlsx, container.config.budget_sheet_name
        )
    container.database.record_run("budget_import", "success", result)
    return jsonify(result)


@api.post("/ynab/sync")
@require_bearer_token
def sync_ynab():
    container = _container()
    with container.operation_lock.guard("ynab_sync"):
        result = container.ynab_sync.sync()
    return jsonify(result)


@api.post("/reconcile")
@require_bearer_token
def reconcile():
    container = _container()
    with container.operation_lock.guard("reconcile"):
        result = container.reconcile.reconcile()
    return jsonify(result)


@api.get("/reports/summary")
@require_bearer_token
def summary():
    month = request.args.get("month")
    return jsonify(_container().reports.summary(month=month))


@api.get("/transactions")
@require_bearer_token
def transactions():
    limit = min(max(int(request.args.get("limit", "50")), 1), 500)
    result = _container().reports.transactions(
        since=request.args.get("since"),
        until=request.args.get("until"),
        group_name=request.args.get("group"),
        category_name=request.args.get("category"),
        limit=limit,
    )
    return jsonify(result)


def register_error_handlers(app) -> None:
    @app.errorhandler(OperationInProgressError)
    def handle_busy(error: OperationInProgressError):
        return jsonify({"error": str(error)}), 409

    @app.errorhandler(ConfigError)
    @app.errorhandler(DataIntegrityError)
    @app.errorhandler(FinclaideError)
    def handle_application_error(error: FinclaideError):
        return jsonify({"error": str(error)}), 400

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception):
        current_app.logger.exception("Unhandled error", exc_info=error)
        return jsonify({"error": "internal_server_error"}), 500
