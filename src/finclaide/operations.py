from __future__ import annotations

from typing import Any


def run_budget_import(container: Any) -> dict[str, Any]:
    result = container.budget_importer.import_budget(
        container.config.budget_xlsx,
        container.config.budget_sheet_name,
    )
    container.database.record_run("budget_import", "success", result)
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
