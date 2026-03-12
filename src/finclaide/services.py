from __future__ import annotations

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

    def status(self) -> dict[str, Any]:
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
        return {
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
        params.append(limit)

        query = f"""
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
            WHERE {' AND '.join(conditions)}
            ORDER BY t.date DESC, t.id DESC
            LIMIT ?
        """
        with self.database.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return {"transactions": [dict(row) for row in rows]}

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


@dataclass
class ServiceContainer:
    config: AppConfig
    database: Database
    budget_importer: Any
    ynab_sync: Any
    reconcile: ReconciliationService
    reports: ReportService
    operation_lock: OperationLock
