from __future__ import annotations

import math
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from finclaide.config import AppConfig
from finclaide.database import Database, utc_now
from finclaide.errors import DataIntegrityError
from finclaide.locking import OperationLock


def _month_bounds(month: str | None) -> tuple[str, str, int, str]:
    if month:
        selected = datetime.strptime(month, "%Y-%m").date()
    else:
        now = datetime.now(UTC).date()
        selected = date(now.year, now.month, 1)
    if selected.month == 12:
        next_month = date(selected.year + 1, 1, 1)
    else:
        next_month = date(selected.year, selected.month + 1, 1)
    return selected.isoformat(), next_month.isoformat(), selected.month, selected.strftime("%Y-%m")


def _iter_month_labels(start_month: str, end_month: str) -> list[str]:
    start = datetime.strptime(start_month, "%Y-%m").date()
    end = datetime.strptime(end_month, "%Y-%m").date()
    labels: list[str] = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        labels.append(cursor.strftime("%Y-%m"))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return labels


def _ceil_div(numerator: int, denominator: int) -> int:
    return math.ceil(numerator / denominator)


def _hours_stale(value: str | None) -> float | None:
    if not value:
        return None
    return round((datetime.now(UTC) - datetime.fromisoformat(value)).total_seconds() / 3600, 1)


def _previous_month_label(month: str) -> str:
    selected = datetime.strptime(month, "%Y-%m").date()
    if selected.month == 1:
        return f"{selected.year - 1:04d}-12"
    return f"{selected.year:04d}-{selected.month - 1:02d}"


@dataclass
class ReconciliationService:
    database: Database

    def preview(self) -> dict[str, Any]:
        with self.database.connect() as connection:
            planned_rows = connection.execute(
                """
                SELECT group_name, category_name
                FROM v_latest_planned_categories
                ORDER BY group_name, category_name
                """
            ).fetchall()
            if not planned_rows:
                raise DataIntegrityError("Cannot preview reconcile before importing a budget.")

            ynab_rows = connection.execute(
                """
                SELECT c.group_name AS group_name, c.name AS category_name
                FROM categories AS c
                JOIN category_groups AS g ON g.id = c.group_id
                WHERE c.deleted = 0
                  AND c.hidden = 0
                  AND g.deleted = 0
                  AND g.hidden = 0
                ORDER BY c.group_name, c.name
                """
            ).fetchall()

        planned_set: set[tuple[str, str]] = {
            (row["group_name"], row["category_name"]) for row in planned_rows
        }
        ynab_set: set[tuple[str, str]] = {
            (row["group_name"], row["category_name"]) for row in ynab_rows
        }

        def to_payload(pairs: set[tuple[str, str]]) -> list[dict[str, str]]:
            return [
                {"group_name": group, "category_name": category}
                for group, category in sorted(pairs)
            ]

        exact_matches = planned_set & ynab_set
        missing_in_ynab = planned_set - ynab_set
        extra_in_ynab = ynab_set - planned_set

        return {
            "previewed_at": utc_now(),
            "planned_count": len(planned_set),
            "ynab_count": len(ynab_set),
            "exact_matches": to_payload(exact_matches),
            "missing_in_ynab": to_payload(missing_in_ynab),
            "extra_in_ynab": to_payload(extra_in_ynab),
            "counts": {
                "exact": len(exact_matches),
                "missing_in_ynab": len(missing_in_ynab),
                "extra_in_ynab": len(extra_in_ynab),
            },
        }

    def reconcile(self) -> dict[str, Any]:
        run_at = utc_now()
        mismatches: list[dict[str, Any]] = []
        finished_at: str | None = None
        try:
            with self.database.connect() as connection:
                planned_rows = connection.execute(
                    """
                    SELECT group_name, category_name
                    FROM v_latest_planned_categories
                    ORDER BY group_name, category_name
                    """
                ).fetchall()
                if not planned_rows:
                    raise DataIntegrityError("Cannot reconcile before importing a budget.")

                for row in planned_rows:
                    category = connection.execute(
                        """
                        SELECT id
                        FROM categories
                        WHERE deleted = 0
                          AND group_name = ?
                          AND name = ?
                        LIMIT 1
                        """,
                        (row["group_name"], row["category_name"]),
                    ).fetchone()
                    if category is None:
                        mismatches.append(
                            {
                                "group_name": row["group_name"],
                                "category_name": row["category_name"],
                                "reason": "Missing exact YNAB category match.",
                            }
                        )

                status = "success" if not mismatches else "failed"
                summary = {"run_at": run_at, "mismatches": mismatches}
                result = connection.execute(
                    """
                    INSERT INTO reconciliation_results(run_at, status, mismatch_count, summary_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (run_at, status, len(mismatches), json.dumps(summary, sort_keys=True)),
                )
                reconciliation_id = int(result.lastrowid)
                for mismatch in mismatches:
                    connection.execute(
                        """
                        INSERT INTO reconciliation_mismatches(reconciliation_id, group_name, category_name, reason)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            reconciliation_id,
                            mismatch["group_name"],
                            mismatch["category_name"],
                            mismatch["reason"],
                        ),
                    )

            finished_at = utc_now()
            if mismatches:
                self.database.record_run(
                    source="reconcile",
                    status="failed",
                    details={
                        "mismatch_count": len(mismatches),
                        "mismatch_preview": mismatches[:5],
                        "error": f"Reconciliation failed with {len(mismatches)} mismatches.",
                    },
                    started_at=run_at,
                    finished_at=finished_at,
                )
                raise DataIntegrityError(f"Reconciliation failed with {len(mismatches)} mismatches.")

            result = {"run_at": run_at, "mismatch_count": 0, "mismatches": []}
            self.database.record_run(
                source="reconcile",
                status="success",
                details=result,
                started_at=run_at,
                finished_at=finished_at,
            )
            return result
        except Exception as error:
            if mismatches:
                raise
            self.database.record_run(
                source="reconcile",
                status="failed",
                details={"mismatch_count": 0, "error": str(error)},
                started_at=run_at,
                finished_at=finished_at or utc_now(),
            )
            raise


@dataclass
class ReportService:
    config: AppConfig
    database: Database
    operation_lock: OperationLock
    scheduled_refresh: Any | None = None

    def status(self, *, include_recent_runs: bool = False) -> dict[str, Any]:
        with self.database.connect() as connection:
            latest_import = connection.execute(
                "SELECT * FROM v_latest_budget_import"
            ).fetchone()
            sync_state = None
            if self.config.ynab_plan_id:
                sync_state = connection.execute(
                    "SELECT * FROM ynab_sync_state WHERE plan_id = ?",
                    (self.config.ynab_plan_id,),
                ).fetchone()
            latest_reconciliation = connection.execute(
                "SELECT * FROM v_latest_reconciliation"
            ).fetchone()
            latest_runs = {}
            if include_recent_runs:
                run_rows = connection.execute(
                    """
                    SELECT id, source, status, started_at, finished_at, details_json
                    FROM sync_runs
                    WHERE id IN (
                        SELECT MAX(id)
                        FROM sync_runs
                        GROUP BY source
                    )
                    ORDER BY id DESC
                    """
                ).fetchall()
                latest_runs = {
                    row["source"]: {
                        "id": row["id"],
                        "status": row["status"],
                        "started_at": row["started_at"],
                        "finished_at": row["finished_at"],
                        "details": json.loads(row["details_json"] or "{}"),
                    }
                    for row in run_rows
                }
        plan_last_updated_at = latest_import["imported_at"] if latest_import else None
        actuals_last_updated_at = sync_state["last_synced_at"] if sync_state else None
        actuals_hours_stale = _hours_stale(actuals_last_updated_at)
        payload = {
            "plan_id": self.config.ynab_plan_id,
            "budget_sheet": self.config.budget_sheet_name,
            "busy": self.operation_lock.current_operation is not None,
            "current_operation": self.operation_lock.current_operation,
            "last_budget_import_at": latest_import["imported_at"] if latest_import else None,
            "last_budget_import_id": latest_import["id"] if latest_import else None,
            "last_ynab_sync_at": sync_state["last_synced_at"] if sync_state else None,
            "last_server_knowledge": sync_state["server_knowledge"] if sync_state else None,
            "last_reconcile_at": latest_reconciliation["run_at"] if latest_reconciliation else None,
            "last_reconcile_status": latest_reconciliation["status"] if latest_reconciliation else None,
            "plan_freshness": {
                "status": "fresh" if latest_import else "missing",
                "last_updated_at": plan_last_updated_at,
                "hours_stale": _hours_stale(plan_last_updated_at),
            },
            "actuals_freshness": {
                "status": (
                    "missing"
                    if actuals_hours_stale is None
                    else "critical"
                    if actuals_hours_stale > 72
                    else "warning"
                    if actuals_hours_stale > 24
                    else "fresh"
                ),
                "last_updated_at": actuals_last_updated_at,
                "hours_stale": actuals_hours_stale,
            },
            "plan_provenance": {
                "source_type": self._plan_source_type(),
                "workbook_path": str(self._plan_workbook_path()),
                "workbook_url": self.config.budget_xlsx_url,
                "google_sheets_file_id": self.config.google_sheets_file_id,
                "sheet_name": self.config.budget_sheet_name,
                "import_id": latest_import["id"] if latest_import else None,
                "imported_at": plan_last_updated_at,
                "last_result": latest_runs.get("budget_import", {}).get("status") if include_recent_runs else None,
            },
            "actuals_provenance": {
                "source_type": "ynab",
                "plan_id": self.config.ynab_plan_id,
                "last_synced_at": actuals_last_updated_at,
                "server_knowledge": sync_state["server_knowledge"] if sync_state else None,
                "last_result": latest_runs.get("ynab_sync", {}).get("status") if include_recent_runs else None,
            },
            "scheduled_refresh": (
                self.scheduled_refresh.snapshot()
                if self.scheduled_refresh is not None
                else {
                    "enabled": False,
                    "interval_minutes": None,
                    "next_run_at": None,
                    "last_started_at": None,
                    "last_finished_at": None,
                    "last_status": None,
                    "last_error": None,
                }
            ),
        }
        if include_recent_runs:
            payload["latest_runs"] = latest_runs
        return payload

    def runs(self, *, limit: int = 20, source: str | None = None) -> dict[str, Any]:
        with self.database.connect() as connection:
            query = """
                SELECT id, source, status, started_at, finished_at, details_json
                FROM sync_runs
            """
            params: list[Any] = []
            if source:
                query += " WHERE source = ?"
                params.append(source)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            rows = connection.execute(query, tuple(params)).fetchall()
        return {
            "runs": [
                {
                    "id": row["id"],
                    "source": row["source"],
                    "status": row["status"],
                    "started_at": row["started_at"],
                    "finished_at": row["finished_at"],
                    "details": json.loads(row["details_json"] or "{}"),
                }
                for row in rows
            ]
        }

    def run_by_id(self, run_id: int) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, source, status, started_at, finished_at, details_json
                FROM sync_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "source": row["source"],
            "status": row["status"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "details": json.loads(row["details_json"] or "{}"),
        }

    def summary(self, month: str | None = None) -> dict[str, Any]:
        month_start, month_end, month_number, month_label = _month_bounds(month)
        with self.database.connect() as connection:
            latest_import = connection.execute("SELECT * FROM v_latest_budget_import").fetchone()
            if latest_import is None:
                return {
                    "as_of": utc_now(),
                    "plan_year": None,
                    "month": month_label,
                    "groups": [],
                    "overage_watch": self._empty_overage_watch(),
                    "recent_transactions": [],
                    "mismatches": [],
                    "sync_status": self.status(),
                }

            planned_rows = connection.execute(
                """
                SELECT
                    pc.group_name,
                    pc.category_name,
                    pc.block,
                    pc.planned_milliunits,
                    pc.annual_target_milliunits,
                    pc.due_month,
                    pc.formula_text,
                    COALESCE(c.balance_milliunits, 0) AS current_balance_milliunits
                FROM v_latest_planned_categories pc
                LEFT JOIN categories c
                  ON c.group_name = pc.group_name
                 AND c.name = pc.category_name
                 AND c.deleted = 0
                ORDER BY pc.group_name, pc.category_name
                """
            ).fetchall()

            actual_rows = connection.execute(
                """
                SELECT
                    COALESCE(c.group_name, t.group_name) AS group_name,
                    COALESCE(c.name, t.category_name) AS category_name,
                    SUM(-1 * t.amount_milliunits) AS actual_milliunits
                FROM transactions t
                LEFT JOIN categories c ON c.id = t.category_id
                WHERE t.deleted = 0
                  AND t.date >= ?
                  AND t.date < ?
                  AND COALESCE(c.group_name, t.group_name) IS NOT NULL
                  AND COALESCE(c.name, t.category_name) IS NOT NULL
                GROUP BY 1, 2
                """,
                (month_start, month_end),
            ).fetchall()
            actual_lookup = {
                (row["group_name"], row["category_name"]): int(row["actual_milliunits"] or 0)
                for row in actual_rows
            }

            mismatch_rows = connection.execute(
                """
                SELECT rm.group_name, rm.category_name, rm.reason
                FROM reconciliation_mismatches rm
                WHERE rm.reconciliation_id = (SELECT id FROM v_latest_reconciliation)
                ORDER BY rm.group_name, rm.category_name
                """
            ).fetchall()

            transactions = connection.execute(
                """
                SELECT
                    t.id,
                    t.date,
                    t.payee_name,
                    t.memo,
                    t.amount_milliunits,
                    COALESCE(c.group_name, t.group_name) AS group_name,
                    COALESCE(c.name, t.category_name) AS category_name
                FROM v_recent_transactions t
                LEFT JOIN categories c ON c.id = t.category_id
                ORDER BY t.date DESC, t.id DESC
                LIMIT 20
                """
            ).fetchall()
            overage_watch = self._overage_watch(
                connection,
                planned_rows=planned_rows,
                analysis_end=month_start,
            )

        group_map: dict[str, dict[str, Any]] = {}
        for row in planned_rows:
            key = (row["group_name"], row["category_name"])
            actual_milliunits = actual_lookup.get(key, 0)
            planned_milliunits = int(row["planned_milliunits"])
            current_balance = int(row["current_balance_milliunits"])
            variance = actual_milliunits - planned_milliunits
            category_status = self._category_status(
                block=row["block"],
                planned_milliunits=planned_milliunits,
                actual_milliunits=actual_milliunits,
                current_balance_milliunits=current_balance,
                annual_target_milliunits=int(row["annual_target_milliunits"]),
                due_month=row["due_month"],
                month_number=month_number,
            )
            group_entry = group_map.setdefault(
                row["group_name"],
                {
                    "group_name": row["group_name"],
                    "categories": [],
                    "planned_milliunits": 0,
                    "actual_milliunits": 0,
                    "variance_milliunits": 0,
                },
            )
            category_entry = {
                "category_name": row["category_name"],
                "planned_milliunits": planned_milliunits,
                "actual_milliunits": actual_milliunits,
                "variance_milliunits": variance,
                "current_balance_milliunits": current_balance,
                "due_month": row["due_month"],
                "status": category_status,
            }
            group_entry["categories"].append(category_entry)
            group_entry["planned_milliunits"] += planned_milliunits
            group_entry["actual_milliunits"] += actual_milliunits
            group_entry["variance_milliunits"] += variance

        return {
            "as_of": utc_now(),
            "plan_year": latest_import["plan_year"],
            "month": month_label,
            "groups": list(group_map.values()),
            "overage_watch": overage_watch,
            "recent_transactions": [dict(row) for row in transactions],
            "mismatches": [dict(row) for row in mismatch_rows],
            "sync_status": self.status(),
        }

    def transactions(
        self,
        since: str | None,
        until: str | None,
        group_name: str | None,
        category_name: str | None,
        limit: int,
    ) -> dict[str, Any]:
        result = self.transactions_page(
            since=since,
            until=until,
            group_name=group_name,
            category_name=category_name,
            query=None,
            limit=limit,
            offset=0,
        )
        return {"transactions": result["transactions"]}

    def transactions_page(
        self,
        *,
        since: str | None,
        until: str | None,
        group_name: str | None,
        category_name: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        conditions = ["t.deleted = 0"]
        params: list[Any] = []
        if since:
            conditions.append("t.date >= ?")
            params.append(since)
        if until:
            conditions.append("t.date <= ?")
            params.append(until)
        if group_name:
            conditions.append("COALESCE(c.group_name, t.group_name) = ?")
            params.append(group_name)
        if category_name:
            conditions.append("COALESCE(c.name, t.category_name) = ?")
            params.append(category_name)
        if query:
            search = f"%{query.lower()}%"
            conditions.append(
                "(LOWER(COALESCE(t.payee_name, '')) LIKE ? OR LOWER(COALESCE(t.memo, '')) LIKE ?)"
            )
            params.extend([search, search])

        where_clause = " AND ".join(conditions)
        rows_query = f"""
            SELECT
                t.id,
                t.date,
                t.payee_name,
                t.memo,
                t.amount_milliunits,
                COALESCE(c.group_name, t.group_name) AS group_name,
                COALESCE(c.name, t.category_name) AS category_name
            FROM transactions t
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE {where_clause}
            ORDER BY t.date DESC, t.id DESC
            LIMIT ?
            OFFSET ?
        """
        count_query = f"""
            SELECT COUNT(*) AS total_count
            FROM transactions t
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE {where_clause}
        """
        with self.database.connect() as connection:
            total_count = int(connection.execute(count_query, tuple(params)).fetchone()["total_count"])
            rows = connection.execute(rows_query, tuple(params + [limit, offset])).fetchall()
        return {
            "transactions": [dict(row) for row in rows],
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }

    def _category_status(
        self,
        *,
        block: str,
        planned_milliunits: int,
        actual_milliunits: int,
        current_balance_milliunits: int,
        annual_target_milliunits: int,
        due_month: int | None,
        month_number: int,
    ) -> str:
        if block in {"annual", "one_time"}:
            target = annual_target_milliunits or planned_milliunits
            if due_month is None:
                expected = min(target, planned_milliunits * month_number)
            elif month_number >= due_month:
                expected = target
            else:
                expected = min(target, planned_milliunits * month_number)
            if current_balance_milliunits >= target and target > 0:
                return "funded"
            if current_balance_milliunits >= expected:
                return "ahead"
            return "behind"
        if actual_milliunits > planned_milliunits:
            return "over"
        if actual_milliunits < planned_milliunits:
            return "under"
        return "on_target"

    def _empty_overage_watch(self) -> dict[str, Any]:
        return {
            "analysis_start_month": None,
            "analysis_end_month": None,
            "analysis_month_count": 0,
            "categories": [],
        }

    def _overage_watch(
        self,
        connection: Any,
        *,
        planned_rows: list[Any],
        analysis_end: str,
    ) -> dict[str, Any]:
        watch_rows = [
            row
            for row in planned_rows
            if row["block"] in {"monthly", "stipends"} and row["group_name"] != "Payments"
        ]
        if not watch_rows:
            return self._empty_overage_watch()

        bounds = connection.execute(
            """
            SELECT MIN(date) AS min_date, MAX(date) AS max_date
            FROM transactions
            WHERE deleted = 0
              AND date < ?
            """,
            (analysis_end,),
        ).fetchone()
        if bounds["min_date"] is None or bounds["max_date"] is None:
            return self._empty_overage_watch()

        analysis_start_month = bounds["min_date"][:7]
        analysis_end_month = bounds["max_date"][:7]
        month_labels = _iter_month_labels(analysis_start_month, analysis_end_month)

        spend_rows = connection.execute(
            """
            SELECT
                substr(t.date, 1, 7) AS month,
                COALESCE(c.group_name, t.group_name) AS group_name,
                COALESCE(c.name, t.category_name) AS category_name,
                SUM(CASE WHEN t.amount_milliunits < 0 THEN -1 * t.amount_milliunits ELSE 0 END) AS spend_milliunits
            FROM transactions t
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE t.deleted = 0
              AND t.date < ?
              AND COALESCE(c.group_name, t.group_name) IS NOT NULL
              AND COALESCE(c.name, t.category_name) IS NOT NULL
            GROUP BY 1, 2, 3
            """,
            (analysis_end,),
        ).fetchall()
        spend_lookup = {
            (row["month"], row["group_name"], row["category_name"]): int(row["spend_milliunits"] or 0)
            for row in spend_rows
        }

        categories: list[dict[str, Any]] = []
        for row in watch_rows:
            series = [
                (
                    label,
                    spend_lookup.get((label, row["group_name"], row["category_name"]), 0),
                )
                for label in month_labels
            ]
            first_active_index = next((index for index, (_, spend) in enumerate(series) if spend > 0), None)
            if first_active_index is None:
                continue

            analysis_series = series[first_active_index:]
            active_months = sum(1 for _, spend in analysis_series if spend > 0)
            if active_months < 2:
                continue

            planned_milliunits = int(row["planned_milliunits"])
            current_balance = int(row["current_balance_milliunits"])
            cumulative_balance = 0
            cumulative_spend = 0
            min_cumulative_balance = 0
            over_months = 0
            peak_month = analysis_series[0][0]
            peak_spend = 0
            required_monthly = 0

            for index, (label, spend) in enumerate(analysis_series, start=1):
                cumulative_spend += spend
                cumulative_balance += planned_milliunits - spend
                min_cumulative_balance = min(min_cumulative_balance, cumulative_balance)
                required_monthly = max(required_monthly, _ceil_div(cumulative_spend, index))
                if spend > planned_milliunits:
                    over_months += 1
                if spend > peak_spend:
                    peak_month = label
                    peak_spend = spend

            shortfall_milliunits = max(0, -1 * min_cumulative_balance)
            suggested_monthly = max(planned_milliunits, required_monthly)
            if shortfall_milliunits < 200_000 and suggested_monthly - planned_milliunits < 50_000:
                continue

            total_spend = sum(spend for _, spend in analysis_series)
            categories.append(
                {
                    "group_name": row["group_name"],
                    "category_name": row["category_name"],
                    "block": row["block"],
                    "watch_level": (
                        "critical"
                        if planned_milliunits == 0
                        or shortfall_milliunits >= 500_000
                        or suggested_monthly - planned_milliunits >= 250_000
                        else "warning"
                    ),
                    "watch_kind": "unplanned" if planned_milliunits == 0 else "underplanned",
                    "planned_milliunits": planned_milliunits,
                    "suggested_monthly_milliunits": suggested_monthly,
                    "average_spend_milliunits": _ceil_div(total_spend, len(analysis_series)),
                    "active_average_spend_milliunits": _ceil_div(total_spend, active_months),
                    "max_spend_milliunits": peak_spend,
                    "peak_month": peak_month,
                    "active_months": active_months,
                    "analysis_month_count": len(analysis_series),
                    "over_months": over_months,
                    "shortfall_milliunits": shortfall_milliunits,
                    "current_balance_milliunits": current_balance,
                }
            )

        categories.sort(
            key=lambda item: (
                item["watch_level"] != "critical",
                -item["shortfall_milliunits"],
                -item["suggested_monthly_milliunits"],
                item["group_name"],
                item["category_name"],
            )
        )
        return {
            "analysis_start_month": analysis_start_month,
            "analysis_end_month": analysis_end_month,
            "analysis_month_count": len(month_labels),
            "categories": categories,
        }

    def _plan_source_type(self) -> str:
        if self.config.budget_source == "google_sheets":
            return "google_sheets"
        if self.config.budget_source == "remote_url":
            return "remote_export"
        return "local_workbook"

    def _plan_workbook_path(self) -> Path:
        if self.config.budget_source == "google_sheets":
            return self.config.budget_xlsx_download_path or self.config.db_path.with_name("Budget.google.xlsx")
        if self.config.budget_source == "remote_url":
            return self.config.budget_xlsx_download_path or self.config.db_path.with_name("Budget.remote.xlsx")
        return self.config.budget_xlsx


@dataclass
class WeeklyReviewService:
    reports: ReportService
    analytics: Any

    def weekly(self, month: str | None = None) -> dict[str, Any]:
        summary = self.reports.summary(month=month)
        status = self.reports.status(include_recent_runs=True)
        month_label = summary["month"]
        prior_month = _previous_month_label(month_label)
        health = self.analytics.financial_health_check()
        comparison = self.analytics.compare_months(prior_month, month_label)
        anomalies = self.analytics.detect_anomalies(months=3, threshold_sigma=2.0, as_of_month=month_label)
        recommendations = self.analytics.budget_recommendations(as_of_month=month_label)

        blockers = self._blockers(status=status, health=health)
        overages = self._overages(summary=summary, month_label=month_label)
        changes = self._changes(comparison=comparison)
        anomaly_items = self._anomalies(anomalies=anomalies, month_label=month_label)
        recommendation_items = self._recommendations(recommendations=recommendations)

        headline = self._headline(
            month_label=month_label,
            blockers=blockers,
            overages=overages,
            changes=changes,
            anomalies=anomaly_items,
            recommendations=recommendation_items,
        )
        overall_status = self._overall_status(
            blockers=blockers,
            overages=overages,
            changes=changes,
            anomalies=anomaly_items,
            recommendations=recommendation_items,
        )

        planned_total = sum(group["planned_milliunits"] for group in summary["groups"])
        actual_total = sum(group["actual_milliunits"] for group in summary["groups"])
        return {
            "month": month_label,
            "generated_at": utc_now(),
            "overall_status": overall_status,
            "headline": headline,
            "blockers": blockers,
            "changes": changes,
            "overages": overages,
            "anomalies": anomaly_items,
            "recommendations": recommendation_items,
            "supporting_metrics": {
                "planned_total_milliunits": planned_total,
                "actual_total_milliunits": actual_total,
                "variance_total_milliunits": actual_total - planned_total,
                "blocker_count": len(blockers),
                "change_count": len(changes),
                "overage_count": len(overages),
                "anomaly_count": len(anomaly_items),
                "recommendation_count": len(recommendation_items),
                "projected_annual_variance_milliunits": recommendations["summary"]["total_projected_variance_milliunits"],
                "categories_over_budget": recommendations["summary"]["categories_over_budget"],
                "categories_under_budget": recommendations["summary"]["categories_under_budget"],
            },
        }

    def _blockers(self, *, status: dict[str, Any], health: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for alert in health["alerts"]:
            if alert["category"] not in {"stale_data", "no_budget", "reconciliation"}:
                continue
            evidence: dict[str, Any] = {"alert_category": alert["category"]}
            recommended_action = None
            if alert["category"] == "stale_data":
                evidence["hours_stale"] = status["actuals_freshness"]["hours_stale"]
                evidence["last_synced_at"] = status["actuals_freshness"]["last_updated_at"]
                recommended_action = "Run YNAB sync before relying on this review."
            elif alert["category"] == "no_budget":
                evidence["last_budget_import_at"] = status["last_budget_import_at"]
                recommended_action = "Import the planning workbook before reviewing category performance."
            elif alert["category"] == "reconciliation":
                evidence["last_reconcile_status"] = status["last_reconcile_status"]
                evidence["mismatch_count"] = (
                    status.get("latest_runs", {})
                    .get("reconcile", {})
                    .get("details", {})
                    .get("mismatch_count")
                )
                recommended_action = "Resolve exact-match category mismatches in YNAB before adjusting the plan."
            items.append(
                {
                    "kind": f"{alert['category']}_blocker",
                    "signal_class": "system",
                    "severity": alert["severity"],
                    "title": alert["title"],
                    "why_it_matters": alert["detail"],
                    "recommended_action": recommended_action,
                    "group_name": None,
                    "category_name": None,
                    "evidence": evidence,
                    "impact_milliunits": 0,
                }
            )
        return sorted(items, key=self._priority_key)

    def _overages(self, *, summary: dict[str, Any], month_label: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for group in summary["groups"]:
            for category in group["categories"]:
                variance = category["variance_milliunits"]
                planned = category["planned_milliunits"]
                actual = category["actual_milliunits"]
                if variance <= 0:
                    continue
                if variance < 50_000 and not (planned == 0 and actual >= 25_000):
                    continue
                severity = self._variance_severity(variance=variance, planned=planned)
                items.append(
                    {
                        "kind": "overage",
                        "signal_class": self._signal_class(group["group_name"], category["category_name"]),
                        "severity": severity,
                        "title": (
                            f"{group['group_name']} / {category['category_name']} is over plan by "
                            f"{self._format_money(variance)} in {month_label}"
                        ),
                        "why_it_matters": (
                            f"Actual spending is {self._format_money(actual)} against a plan of "
                            f"{self._format_money(planned)}."
                        ),
                        "recommended_action": (
                            "Review recent transactions and decide whether to cut back or raise the category target."
                        ),
                        "group_name": group["group_name"],
                        "category_name": category["category_name"],
                        "evidence": {
                            "month": month_label,
                            "planned_milliunits": planned,
                            "actual_milliunits": actual,
                            "variance_milliunits": variance,
                        },
                        "impact_milliunits": variance,
                    }
                )
        return sorted(items, key=self._priority_key)

    def _changes(self, *, comparison: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for category in comparison["categories"]:
            delta = category["delta_milliunits"]
            if abs(delta) < 75_000:
                continue
            delta_percent = category["delta_percent"]
            direction = "up" if delta > 0 else "down"
            severity = (
                "warning"
                if abs(delta) >= 250_000 or (delta_percent is not None and abs(delta_percent) >= 50)
                else "info"
            )
            items.append(
                {
                    "kind": "month_change",
                    "signal_class": self._signal_class(category["group_name"], category["category_name"]),
                    "severity": severity,
                    "title": (
                        f"{category['group_name']} / {category['category_name']} is {direction} "
                        f"{self._format_money(abs(delta))} versus {comparison['month_a']}"
                    ),
                    "why_it_matters": (
                        f"{comparison['month_b']} spend was {self._format_money(category['month_b_milliunits'])}; "
                        f"{comparison['month_a']} was {self._format_money(category['month_a_milliunits'])}."
                    ),
                    "recommended_action": (
                        "Confirm whether this is a durable behavior change before adjusting the budget baseline."
                    ),
                    "group_name": category["group_name"],
                    "category_name": category["category_name"],
                    "evidence": {
                        "month_a": comparison["month_a"],
                        "month_b": comparison["month_b"],
                        "month_a_milliunits": category["month_a_milliunits"],
                        "month_b_milliunits": category["month_b_milliunits"],
                        "delta_milliunits": delta,
                        "delta_percent": delta_percent,
                    },
                    "impact_milliunits": abs(delta),
                }
            )
        return sorted(items, key=self._priority_key)

    def _anomalies(self, *, anomalies: dict[str, Any], month_label: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for anomaly in anomalies["transaction_anomalies"]:
            if not anomaly["date"].startswith(month_label):
                continue
            amount = abs(anomaly["amount_milliunits"])
            items.append(
                {
                    "kind": "transaction_anomaly",
                    "signal_class": self._signal_class(anomaly["group_name"], anomaly["category_name"]),
                    "severity": "warning" if anomaly["sigma_distance"] >= 3 else "info",
                    "title": (
                        f"{anomaly['payee_name'] or 'Transaction'} looks unusual in "
                        f"{anomaly['group_name'] or 'Uncategorized'} / {anomaly['category_name'] or 'Uncategorized'}"
                    ),
                    "why_it_matters": (
                        f"{self._format_money(amount)} is {anomaly['sigma_distance']}σ above the category's typical transaction size."
                    ),
                    "recommended_action": "Verify whether this was intentional and whether it should change the category plan.",
                    "group_name": anomaly["group_name"] or None,
                    "category_name": anomaly["category_name"] or None,
                    "evidence": {
                        "date": anomaly["date"],
                        "amount_milliunits": anomaly["amount_milliunits"],
                        "sigma_distance": anomaly["sigma_distance"],
                        "category_mean_milliunits": anomaly["category_mean_milliunits"],
                        "category_stddev_milliunits": anomaly["category_stddev_milliunits"],
                    },
                    "impact_milliunits": amount,
                }
            )
        return sorted(items, key=self._priority_key)

    def _recommendations(self, *, recommendations: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for recommendation in recommendations["recommendations"]:
            signal_class = self._signal_class(
                recommendation["group_name"],
                recommendation["category_name"],
            )
            severity = "warning" if abs(recommendation["projected_annual_impact_milliunits"]) >= 5_000_000 else "info"
            items.append(
                {
                    "kind": "budget_recommendation",
                    "signal_class": signal_class,
                    "severity": severity,
                    "title": (
                        f"{recommendation['group_name']} / {recommendation['category_name']}: "
                        f"{recommendation['action'].replace('_', ' ')} to "
                        f"{self._format_money(recommendation['suggested_planned_milliunits'])}/mo"
                    ),
                    "why_it_matters": recommendation["reason"],
                    "recommended_action": (
                        "Adjust the planned category amount only if the recent run rate reflects real expected behavior."
                    ),
                    "group_name": recommendation["group_name"],
                    "category_name": recommendation["category_name"],
                    "evidence": {
                        "action": recommendation["action"],
                        "current_planned_milliunits": recommendation["current_planned_milliunits"],
                        "suggested_planned_milliunits": recommendation["suggested_planned_milliunits"],
                        "projected_annual_impact_milliunits": recommendation["projected_annual_impact_milliunits"],
                        "confidence": recommendation["confidence"],
                        "trend_direction": recommendation["trend_direction"],
                    },
                    "impact_milliunits": abs(recommendation["projected_annual_impact_milliunits"]),
                }
            )
        return sorted(items, key=self._priority_key)

    def _headline(
        self,
        *,
        month_label: str,
        blockers: list[dict[str, Any]],
        overages: list[dict[str, Any]],
        changes: list[dict[str, Any]],
        anomalies: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> str:
        if blockers:
            return blockers[0]["title"]
        if overages:
            return overages[0]["title"]
        if changes:
            return changes[0]["title"]
        if anomalies:
            return anomalies[0]["title"]
        if recommendations:
            return recommendations[0]["title"]
        return f"No material issues were flagged for {month_label}."

    def _overall_status(
        self,
        *,
        blockers: list[dict[str, Any]],
        overages: list[dict[str, Any]],
        changes: list[dict[str, Any]],
        anomalies: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> str:
        severities = [
            item["severity"]
            for item in [*blockers, *overages, *changes, *anomalies, *recommendations]
        ]
        if "critical" in severities:
            return "critical"
        if "warning" in severities:
            return "warning"
        return "healthy"

    def _signal_class(self, group_name: str | None, category_name: str | None) -> str:
        normalized_group = (group_name or "").strip().lower()
        normalized_category = (category_name or "").strip().lower()
        if not normalized_group or not normalized_category:
            return "uncategorized"
        if normalized_group == "internal master category" or normalized_category.startswith("inflow:"):
            return "uncategorized"
        if normalized_group == "payments":
            return "payment_flow"
        if "reimbursement" in normalized_group or "reimbursement" in normalized_category:
            return "reimbursement_flow"
        if normalized_group == "one time purchase" or normalized_category in {"not budgetted", "annual expense"}:
            return "one_off"
        return "core_spend"

    def _priority_key(self, item: dict[str, Any]) -> tuple[int, int, int, str]:
        severity_rank = {"critical": 0, "warning": 1, "info": 2}
        signal_rank = {
            "system": 0,
            "core_spend": 0,
            "payment_flow": 1,
            "reimbursement_flow": 1,
            "one_off": 2,
            "uncategorized": 2,
        }
        impact = int(item.get("impact_milliunits", 0))
        return (
            severity_rank.get(item["severity"], 99),
            signal_rank.get(item.get("signal_class", "core_spend"), 99),
            -impact,
            item["title"],
        )

    def _variance_severity(self, *, variance: int, planned: int) -> str:
        if variance >= 250_000 or (planned == 0 and variance >= 100_000):
            return "critical"
        if variance >= 100_000 or (planned > 0 and variance >= planned // 2):
            return "warning"
        return "info"

    def _format_money(self, milliunits: int) -> str:
        dollars = milliunits / 1000
        sign = "-" if dollars < 0 else ""
        return f"{sign}${abs(dollars):,.2f}"


@dataclass
class ServiceContainer:
    config: AppConfig
    database: Database
    budget_importer: Any
    budget_workbook_source: Any
    ynab_sync: Any
    reconcile: ReconciliationService
    reports: ReportService
    analytics: Any
    review: Any
    scheduled_refresh: Any | None
    operation_lock: OperationLock
