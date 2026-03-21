from __future__ import annotations

import math
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
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


@dataclass
class ReconciliationService:
    database: Database

    def reconcile(self) -> dict[str, Any]:
        run_at = utc_now()
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

            mismatches = []
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

        self.database.record_run(
            source="reconcile",
            status=status,
            details={"mismatch_count": len(mismatches)},
            started_at=run_at,
            finished_at=utc_now(),
        )
        if mismatches:
            raise DataIntegrityError(f"Reconciliation failed with {len(mismatches)} mismatches.")
        return {"run_at": run_at, "mismatch_count": 0, "mismatches": []}


@dataclass
class ReportService:
    config: AppConfig
    database: Database
    operation_lock: OperationLock

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
                    SELECT source, status, started_at, finished_at, details_json
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
                        "status": row["status"],
                        "started_at": row["started_at"],
                        "finished_at": row["finished_at"],
                        "details": json.loads(row["details_json"] or "{}"),
                    }
                    for row in run_rows
                }
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
        }
        if include_recent_runs:
            payload["latest_runs"] = latest_runs
        return payload

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


@dataclass
class ServiceContainer:
    config: AppConfig
    database: Database
    budget_importer: Any
    ynab_sync: Any
    reconcile: ReconciliationService
    reports: ReportService
    analytics: Any
    operation_lock: OperationLock
