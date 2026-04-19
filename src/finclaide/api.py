from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from finclaide.auth import require_bearer_token
from finclaide.errors import (
    ConfigError,
    DataIntegrityError,
    FinclaideError,
    NotFoundError,
    OperationInProgressError,
)
from finclaide.operations import run_budget_import, run_reconcile, run_ynab_sync

api = Blueprint("api", __name__, url_prefix="/api")


def _container():
    return current_app.extensions["finclaide"]


@api.get("/status")
@require_bearer_token
def status():
    return jsonify(_container().reports.status(include_recent_runs=True))


@api.get("/runs")
@require_bearer_token
def runs():
    limit = min(max(int(request.args.get("limit", "20")), 1), 100)
    return jsonify(_container().reports.runs(limit=limit, source=request.args.get("source")))


@api.get("/runs/<int:run_id>")
@require_bearer_token
def run_detail(run_id: int):
    result = _container().reports.run_by_id(run_id)
    if result is None:
        return jsonify({"error": "not_found", "error_detail": {"kind": "not_found", "message": f"Run {run_id} does not exist."}}), 404
    return jsonify(result)


@api.get("/reconcile/preview")
@require_bearer_token
def reconcile_preview():
    return jsonify(_container().reconcile.preview())


@api.post("/budget/import")
@require_bearer_token
def import_budget():
    container = _container()
    with container.operation_lock.guard("budget_import"):
        result = run_budget_import(container)
    return jsonify(result)


@api.post("/ynab/sync")
@require_bearer_token
def sync_ynab():
    container = _container()
    with container.operation_lock.guard("ynab_sync"):
        result = run_ynab_sync(container)
    return jsonify(result)


@api.post("/reconcile")
@require_bearer_token
def reconcile():
    container = _container()
    with container.operation_lock.guard("reconcile"):
        result = run_reconcile(container)
    return jsonify(result)


@api.get("/reports/summary")
@require_bearer_token
def summary():
    month = request.args.get("month")
    return jsonify(_container().reports.summary(month=month))


@api.get("/review/weekly")
@require_bearer_token
def weekly_review():
    return jsonify(_container().review.weekly(month=request.args.get("month")))


@api.get("/plan/active")
@require_bearer_token
def plan_active():
    year_arg = request.args.get("year")
    plan_year = int(year_arg) if year_arg else None
    return jsonify(_container().plan.get_active_plan(plan_year=plan_year))


@api.post("/plan/categories")
@require_bearer_token
def plan_create_category():
    body = request.get_json(force=True, silent=True) or {}
    if "plan_id" not in body:
        return jsonify({"error": "plan_id is required"}), 400
    plan_id = int(body.pop("plan_id"))
    return jsonify(_container().plan.create_category(plan_id, body)), 201


@api.patch("/plan/categories/<int:category_id>")
@require_bearer_token
def plan_update_category(category_id: int):
    body = request.get_json(force=True, silent=True) or {}
    if "plan_id" not in body:
        return jsonify({"error": "plan_id is required"}), 400
    plan_id = int(body.pop("plan_id"))
    if "rename" in body:
        rename = body.pop("rename")
        new_group = rename.get("group_name")
        new_name = rename.get("category_name")
        if new_group is None or new_name is None:
            return jsonify({"error": "rename requires group_name and category_name"}), 400
        result = _container().plan.rename_category(plan_id, category_id, new_group, new_name)
        if body:
            result = _container().plan.update_category(plan_id, category_id, body)
        return jsonify(result)
    return jsonify(_container().plan.update_category(plan_id, category_id, body))


@api.delete("/plan/categories/<int:category_id>")
@require_bearer_token
def plan_delete_category(category_id: int):
    plan_id_arg = request.args.get("plan_id")
    if plan_id_arg is None:
        return jsonify({"error": "plan_id is required"}), 400
    plan_id = int(plan_id_arg)
    _container().plan.delete_category(plan_id, category_id)
    return ("", 204)


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
        return jsonify({"error": str(error), "error_detail": {"kind": "operation_in_progress", "message": str(error)}}), 409

    @app.errorhandler(NotFoundError)
    def handle_not_found(error: NotFoundError):
        return jsonify({"error": "not_found", "error_detail": {"kind": "not_found", "message": str(error)}}), 404

    @app.errorhandler(ConfigError)
    @app.errorhandler(DataIntegrityError)
    @app.errorhandler(FinclaideError)
    def handle_application_error(error: FinclaideError):
        return jsonify({"error": str(error), "error_detail": {"kind": "application_error", "message": str(error)}}), 400

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception):
        current_app.logger.exception("Unhandled error", exc_info=error)
        return jsonify({"error": "internal_server_error", "error_detail": {"kind": "internal_error", "message": "internal_server_error"}}), 500
