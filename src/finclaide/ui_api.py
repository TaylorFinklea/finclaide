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
        if request.method != "DELETE" and not request.is_json:
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


@ui_api.get("/runs/<int:run_id>")
@require_same_origin
def run_detail(run_id: int):
    result = _container().reports.run_by_id(run_id)
    if result is None:
        return jsonify({"error": "not_found", "error_detail": {"kind": "not_found", "message": f"Run {run_id} does not exist."}}), 404
    return jsonify(result)


@ui_api.get("/reconcile/preview")
@require_same_origin
def reconcile_preview():
    return jsonify(_container().reconcile.preview())


@ui_api.get("/summary")
@require_same_origin
def summary():
    month = request.args.get("month")
    return jsonify(_container().reports.summary(month=month))


@ui_api.get("/review/weekly")
@require_same_origin
def weekly_review():
    return jsonify(_container().review.weekly(month=request.args.get("month")))


@ui_api.get("/plan/active")
@require_same_origin
def plan_active():
    year_arg = request.args.get("year")
    plan_year = int(year_arg) if year_arg else None
    return jsonify(_container().plan.get_active_plan(plan_year=plan_year))


@ui_api.post("/plan/categories")
@require_ui_write_request
def plan_create_category():
    body = request.get_json(silent=True) or {}
    if "plan_id" not in body:
        return jsonify({"error": "plan_id is required"}), 400
    plan_id = int(body.pop("plan_id"))
    return jsonify(_container().plan.create_category(plan_id, body)), 201


@ui_api.patch("/plan/categories/<int:category_id>")
@require_ui_write_request
def plan_update_category(category_id: int):
    body = request.get_json(silent=True) or {}
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


@ui_api.delete("/plan/categories/<int:category_id>")
@require_ui_write_request
def plan_delete_category(category_id: int):
    plan_id_arg = request.args.get("plan_id")
    if plan_id_arg is None:
        return jsonify({"error": "plan_id is required"}), 400
    plan_id = int(plan_id_arg)
    _container().plan.delete_category(plan_id, category_id)
    return ("", 204)


@ui_api.get("/plan/revisions")
@require_same_origin
def plan_revisions_list():
    plan_id_arg = request.args.get("plan_id")
    if plan_id_arg is None:
        return jsonify({"error": "plan_id is required"}), 400
    plan_id = int(plan_id_arg)
    limit = min(max(int(request.args.get("limit", "50")), 1), 200)
    return jsonify({"revisions": _container().plan.list_revisions(plan_id, limit=limit)})


@ui_api.get("/plan/revisions/<int:revision_id>")
@require_same_origin
def plan_revision_detail(revision_id: int):
    return jsonify(_container().plan.get_revision(revision_id))


@ui_api.post("/plan/revisions/<int:revision_id>/restore")
@require_ui_write_request
def plan_revision_restore(revision_id: int):
    container = _container()
    with container.operation_lock.guard("plan_restore"):
        result = container.plan.restore_revision(revision_id)
    return jsonify({"plan": result})


@ui_api.get("/scenarios")
@require_same_origin
def scenarios_list():
    return jsonify({"scenarios": _container().plan.list_scenarios()})


@ui_api.get("/scenarios/<int:scenario_id>")
@require_same_origin
def scenario_detail(scenario_id: int):
    return jsonify(_container().plan.get_active_plan_by_id(scenario_id))


@ui_api.post("/scenarios")
@require_ui_write_request
def scenario_create():
    body = request.get_json(silent=True) or {}
    if "from_plan_id" not in body:
        return jsonify({"error": "from_plan_id is required"}), 400
    from_plan_id = int(body["from_plan_id"])
    label = body.get("label")
    return jsonify(
        _container().plan.create_scenario(from_plan_id, label=label)
    ), 201


@ui_api.post("/scenarios/<int:scenario_id>/commit")
@require_ui_write_request
def scenario_commit(scenario_id: int):
    container = _container()
    with container.operation_lock.guard("plan_commit"):
        result = container.plan.commit_scenario(scenario_id)
    return jsonify({"plan": result})


@ui_api.delete("/scenarios/<int:scenario_id>")
@require_same_origin
def scenario_delete(scenario_id: int):
    if request.headers.get("X-Finclaide-UI") != "1":
        return jsonify({"error": "missing_ui_header"}), 403
    _container().plan.discard_scenario(scenario_id)
    return ("", 204)


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
