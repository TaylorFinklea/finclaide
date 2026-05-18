from __future__ import annotations

from functools import wraps
from typing import Any, Callable
from urllib.parse import urlparse

from flask import Blueprint, Response, current_app, jsonify, request, send_file

from finclaide.api import _ai_stream_response
from finclaide.errors import DataIntegrityError
from finclaide.operations import (
    run_budget_export,
    run_budget_import,
    run_budget_publish,
    run_reconcile,
    run_ynab_sync,
)

ui_api = Blueprint("ui_api", __name__, url_prefix="/ui-api")


def _container():
    return current_app.extensions["finclaide"]


def _request_origin() -> str:
    return request.headers.get("Origin", "").rstrip("/")


def _request_origin_host(origin: str) -> str:
    if not origin:
        return ""
    parsed = urlparse(origin)
    return parsed.netloc.lower()


def _expected_hosts() -> set[str]:
    hosts = {
        value.split(",", 1)[0].strip().lower()
        for value in {
            request.host,
            request.headers.get("X-Forwarded-Host", ""),
        }
        if value
    }
    return {host for host in hosts if host}


def _is_ingress_request() -> bool:
    return bool(
        request.headers.get("X-Ingress-Path")
        or request.headers.get("X-Forwarded-Prefix")
    )


def require_same_origin(handler: Callable[..., Response]):
    @wraps(handler)
    def wrapped(*args: Any, **kwargs: Any):
        origin = _request_origin()
        origin_host = _request_origin_host(origin)
        if origin_host and origin_host not in _expected_hosts() and not _is_ingress_request():
            return jsonify({"error": "forbidden"}), 403
        fetch_site = request.headers.get("Sec-Fetch-Site", "")
        if fetch_site and fetch_site not in {"same-origin", "same-site", "none"}:
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


@ui_api.post("/reconcile/apply-plan-to-ynab")
@require_ui_write_request
def reconcile_apply_plan_to_ynab():
    body = request.get_json(silent=True) or {}
    operation = body.get("operation")
    target = body.get("target") or {}
    source = body.get("source") or {}
    if operation not in {"create_category", "rename_category"}:
        return jsonify({"error": "operation must be create_category or rename_category"}), 400
    if not target.get("group_name") or not target.get("category_name"):
        return jsonify({"error": "target requires group_name and category_name"}), 400
    if operation == "rename_category" and (
        not source.get("group_name") or not source.get("category_name")
    ):
        return jsonify({"error": "source requires group_name and category_name"}), 400
    container = _container()
    with container.operation_lock.guard("reconcile_remediation"):
        result = container.reconcile.apply_plan_to_ynab(
            operation=operation,
            group_name=target["group_name"],
            category_name=target["category_name"],
            source_group_name=source.get("group_name"),
            source_category_name=source.get("category_name"),
        )
    return jsonify(result)


@ui_api.get("/summary")
@require_same_origin
def summary():
    month = request.args.get("month")
    return jsonify(_container().reports.summary(month=month))


@ui_api.get("/review/weekly")
@require_same_origin
def weekly_review():
    return jsonify(_container().review.weekly(month=request.args.get("month")))


@ui_api.get("/analytics/pace")
@require_same_origin
def analytics_pace():
    return jsonify(
        _container().analytics.month_pace(month=request.args.get("month"))
    )


@ui_api.get("/analytics/projection")
@require_same_origin
def analytics_projection():
    return jsonify(
        _container().analytics.year_end_projection(
            as_of_month=request.args.get("as_of_month"),
        )
    )


@ui_api.get("/analytics/trends")
@require_same_origin
def analytics_trends():
    months = int(request.args.get("months", "12"))
    return jsonify(
        _container().analytics.spending_trends(
            months=months,
            group_name=request.args.get("group"),
            category_name=request.args.get("category"),
            as_of_month=request.args.get("as_of_month"),
        )
    )


@ui_api.get("/analytics/cashflow")
@require_same_origin
def analytics_cashflow():
    months = int(request.args.get("months", "12"))
    return jsonify(
        _container().analytics.cash_flow_timeline(
            months=months,
            as_of_month=request.args.get("as_of_month"),
        )
    )


@ui_api.get("/analytics/cashflow/recommendations")
@require_same_origin
def analytics_cashflow_recommendations():
    months = int(request.args.get("months", "12"))
    return jsonify(
        _container().analytics.cash_flow_recommendations(
            months=months,
            as_of_month=request.args.get("as_of_month"),
        )
    )


@ui_api.get("/analytics/cashflow/rebalance-prompts")
@require_same_origin
def analytics_cashflow_rebalance_prompts():
    months = int(request.args.get("months", "12"))
    return jsonify(
        _container().analytics.cash_flow_rebalance_prompts(
            months=months,
            as_of_month=request.args.get("as_of_month"),
        )
    )


@ui_api.get("/analytics/anomalies")
@require_same_origin
def analytics_anomalies():
    months = int(request.args.get("months", "6"))
    threshold = float(request.args.get("threshold", "2.0"))
    return jsonify(
        _container().analytics.detect_anomalies(
            months=months,
            threshold_sigma=threshold,
            as_of_month=request.args.get("as_of_month"),
        )
    )


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


@ui_api.post("/scenarios/<int:scenario_id>/save")
@require_ui_write_request
def scenario_save(scenario_id: int):
    body = request.get_json(silent=True) or {}
    if "label" not in body:
        return jsonify({"error": "label is required"}), 400
    container = _container()
    with container.operation_lock.guard("plan_save"):
        result = container.plan.save_scenario(scenario_id, body["label"])
    return jsonify({"plan": result})


@ui_api.post("/scenarios/<int:scenario_id>/fork")
@require_ui_write_request
def scenario_fork(scenario_id: int):
    container = _container()
    with container.operation_lock.guard("plan_fork"):
        result = container.plan.fork_scenario(scenario_id)
    return jsonify(result), 201


@ui_api.post("/scenarios/compare")
@require_ui_write_request
def scenario_compare():
    body = request.get_json(silent=True) or {}
    scenario_id = body.get("scenario_id")
    projection = body.get("projection")
    if (scenario_id is None) == (projection is None):
        return jsonify({"error": "Provide either scenario_id or projection (not both)."}), 400
    plan_svc = _container().plan
    if scenario_id is not None:
        return jsonify(plan_svc.compare_scenario(int(scenario_id)))
    assert projection is not None  # narrowed by the XOR guard above
    axes = projection.get("axes", []) or []
    new_lines = projection.get("new_lines", []) or []
    return jsonify(plan_svc.compare_projection(axes, new_lines))


@ui_api.post("/scenarios/projection/apply-to-sandbox")
@require_ui_write_request
def scenario_projection_apply():
    body = request.get_json(silent=True) or {}
    axes = body.get("axes", []) or []
    new_lines = body.get("new_lines", []) or []
    container = _container()
    with container.operation_lock.guard("plan_apply_projection"):
        try:
            plan = container.plan.apply_projection_to_sandbox(axes, new_lines)
        except DataIntegrityError as exc:
            return jsonify({"error": str(exc)}), 400
    return jsonify(plan), 201


@ui_api.delete("/scenarios/<int:scenario_id>")
@require_same_origin
def scenario_delete(scenario_id: int):
    if request.headers.get("X-Finclaide-UI") != "1":
        return jsonify({"error": "missing_ui_header"}), 403
    _container().plan.discard_scenario(scenario_id)
    return ("", 204)


@ui_api.post("/ai/chat")
@require_ui_write_request
def ai_chat():
    return _ai_stream_response()


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


@ui_api.post("/operations/export-budget")
@require_ui_write_request
def export_budget():
    container = _container()
    with container.operation_lock.guard("budget_export"):
        result = run_budget_export(container)
    return jsonify(result), 201


@ui_api.post("/operations/publish-budget")
@require_ui_write_request
def publish_budget():
    container = _container()
    with container.operation_lock.guard("budget_publish"):
        result = run_budget_publish(container)
    return jsonify(result), 201


@ui_api.get("/operations/export-budget/<int:run_id>/download")
@require_same_origin
def download_budget_export(run_id: int):
    container = _container()
    storage_path = container.export_storage.path_for(run_id)
    if not storage_path.exists():
        return jsonify({"error": "not_found", "error_detail": {"kind": "not_found", "message": f"Export {run_id} is no longer available."}}), 404
    run = container.reports.run_by_id(run_id)
    download_name = (
        run["details"].get("filename")
        if run and isinstance(run.get("details"), dict)
        else f"budget-export-{run_id}.xlsx"
    )
    return send_file(
        storage_path,
        as_attachment=True,
        download_name=download_name,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


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
    # Per the source-of-truth model: app owns the plan, YNAB owns
    # actuals, the workbook is a one-way artifact. Refresh All syncs
    # YNAB + reconciles against the in-app plan. Use "Restore from
    # workbook" if you really need to overwrite the plan.
    container = _container()
    month = (request.get_json(silent=True) or {}).get("month")
    with container.operation_lock.guard("refresh_all"):
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
                "ynab_sync": ynab_sync,
                "status": container.reports.status(include_recent_runs=True),
                "summary": container.reports.summary(month=month),
            }
        )
    return jsonify(payload), status_code
