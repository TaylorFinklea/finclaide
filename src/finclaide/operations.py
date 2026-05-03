from __future__ import annotations

from typing import Any

from finclaide.database import utc_now


def _run_with_tracking(container: Any, source: str, callback) -> dict[str, Any]:
    started_at = utc_now()
    try:
        result = callback()
    except Exception as error:
        container.database.record_run(
            source,
            "failed",
            {"source": source, "error": str(error)},
            started_at=started_at,
            finished_at=utc_now(),
        )
        raise
    container.database.record_run(
        source,
        "success",
        result,
        started_at=started_at,
        finished_at=utc_now(),
    )
    return result


def run_budget_import(container: Any) -> dict[str, Any]:
    started_at = utc_now()
    source_details = container.budget_workbook_source.describe()
    try:
        source_details = container.budget_workbook_source.prepare()
        result = container.budget_importer.import_budget(
            container.budget_workbook_source.current_path(),
            container.config.budget_sheet_name,
        )
    except Exception as error:
        container.database.record_run(
            "budget_import",
            "failed",
            {**source_details, "source": "budget_import", "error": str(error)},
            started_at=started_at,
            finished_at=utc_now(),
        )
        raise
    container.database.record_run(
        "budget_import",
        "success",
        {**source_details, **result},
        started_at=started_at,
        finished_at=utc_now(),
    )
    return result


def run_ynab_sync(container: Any) -> dict[str, Any]:
    return container.ynab_sync.sync()


def run_reconcile(container: Any) -> dict[str, Any]:
    return container.reconcile.reconcile()


def run_refresh_all(container: Any, month: str | None = None) -> dict[str, Any]:
    """Sync YNAB + reconcile against the in-app plan.

    Does NOT re-import from the workbook. SQLite owns the plan now;
    importing on every refresh would clobber in-app edits. Use the
    explicit "Restore from workbook" action when you actually want
    to overwrite the plan from the artifact."""
    ynab_sync = run_ynab_sync(container)
    reconcile = run_reconcile(container)
    return {
        "ynab_sync": ynab_sync,
        "reconcile": reconcile,
        "status": container.reports.status(include_recent_runs=True),
        "summary": container.reports.summary(month=month),
    }


def run_budget_export(container: Any) -> dict[str, Any]:
    started_at = utc_now()
    try:
        result = container.plan_exporter.export_active_plan(
            sheet_name=container.config.budget_sheet_name,
        )
    except Exception as error:
        container.database.record_run(
            "budget_export",
            "failed",
            {"source": "budget_export", "error": str(error)},
            started_at=started_at,
            finished_at=utc_now(),
        )
        raise
    file_size_bytes = len(result.bytes)
    details = {
        "source": "budget_export",
        "filename": result.filename,
        "row_count": result.row_count,
        "file_size_bytes": file_size_bytes,
    }
    run_id = container.database.record_run(
        "budget_export",
        "success",
        details,
        started_at=started_at,
        finished_at=utc_now(),
    )
    container.export_storage.write(run_id, result.bytes)
    return {
        "run_id": run_id,
        "filename": result.filename,
        "row_count": result.row_count,
        "file_size_bytes": file_size_bytes,
    }


def run_budget_publish(container: Any) -> dict[str, Any]:
    started_at = utc_now()
    try:
        result = container.sheets_publisher.publish()
    except Exception as error:
        container.database.record_run(
            "budget_publish",
            "failed",
            {"source": "budget_publish", "error": str(error)},
            started_at=started_at,
            finished_at=utc_now(),
        )
        raise
    details = {
        "source": "budget_publish",
        "spreadsheet_id": result.spreadsheet_id,
        "tab_name": result.tab_name,
        "tab_id": result.tab_id,
        "tab_url": result.tab_url,
        "row_count": result.row_count,
        "file_size_bytes": result.file_size_bytes,
    }
    run_id = container.database.record_run(
        "budget_publish",
        "success",
        details,
        started_at=started_at,
        finished_at=utc_now(),
    )
    return {
        "run_id": run_id,
        "tab_name": result.tab_name,
        "tab_id": result.tab_id,
        "tab_url": result.tab_url,
        "spreadsheet_id": result.spreadsheet_id,
        "row_count": result.row_count,
    }
