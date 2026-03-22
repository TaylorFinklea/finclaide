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
    budget_import = run_budget_import(container)
    ynab_sync = run_ynab_sync(container)
    reconcile = run_reconcile(container)
    return {
        "budget_import": budget_import,
        "ynab_sync": ynab_sync,
        "reconcile": reconcile,
        "status": container.reports.status(include_recent_runs=True),
        "summary": container.reports.summary(month=month),
    }
