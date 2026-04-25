from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from finclaide.database import Database, utc_now
from finclaide.errors import DataIntegrityError, NotFoundError


VALID_BLOCKS = {"monthly", "annual", "one_time", "stipends", "savings"}
EDITABLE_FIELDS = {"planned_milliunits", "annual_target_milliunits", "due_month", "notes"}
VALID_REVISION_SOURCES = {
    "ui_create",
    "ui_update",
    "ui_delete",
    "ui_rename",
    "importer",
    "migration",
    "restore",
}
# Retain the most recent N revisions per plan, plus anything newer than RETENTION_DAYS,
# whichever set is larger. Prune runs after every revision insert.
RETENTION_KEEP_RECENT = 50
RETENTION_KEEP_DAYS = 7


@dataclass
class PlanService:
    database: Database

    def get_active_plan(self, plan_year: int | None = None) -> dict[str, Any]:
        with self.database.connect() as connection:
            if plan_year is None:
                plan_row = connection.execute(
                    """
                    SELECT * FROM plans
                    WHERE status = 'active'
                    ORDER BY plan_year DESC, id DESC
                    LIMIT 1
                    """
                ).fetchone()
            else:
                plan_row = connection.execute(
                    """
                    SELECT * FROM plans
                    WHERE status = 'active' AND plan_year = ?
                    LIMIT 1
                    """,
                    (plan_year,),
                ).fetchone()
            if plan_row is None:
                raise NotFoundError("No active plan exists.")

            category_rows = connection.execute(
                """
                SELECT * FROM plan_categories
                WHERE plan_id = ?
                ORDER BY group_name, category_name
                """,
                (plan_row["id"],),
            ).fetchall()

        return _shape_plan_payload(plan_row, category_rows)

    def create_category(self, plan_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        group_name = _required_text(fields, "group_name")
        category_name = _required_text(fields, "category_name")
        block = fields.get("block")
        if block not in VALID_BLOCKS:
            raise DataIntegrityError(
                f"Invalid block '{block}'. Must be one of: {sorted(VALID_BLOCKS)}."
            )
        planned_milliunits = _coerce_milliunits(fields.get("planned_milliunits", 0), "planned_milliunits")
        annual_target_milliunits = _coerce_milliunits(
            fields.get("annual_target_milliunits", 0), "annual_target_milliunits"
        )
        due_month = _coerce_due_month(fields.get("due_month"))
        notes = fields.get("notes")
        if notes is not None:
            notes = str(notes)

        now = utc_now()
        try:
            with self.database.connect() as connection:
                self._ensure_plan_exists(connection, plan_id)
                cursor = connection.execute(
                    """
                    INSERT INTO plan_categories(
                        plan_id, group_name, category_name, block,
                        planned_milliunits, annual_target_milliunits, due_month,
                        notes, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plan_id,
                        group_name,
                        category_name,
                        block,
                        planned_milliunits,
                        annual_target_milliunits,
                        due_month,
                        notes,
                        now,
                        now,
                    ),
                )
                new_id = int(cursor.lastrowid)
                self._touch_plan(connection, plan_id, now)
                row = connection.execute(
                    "SELECT * FROM plan_categories WHERE id = ?", (new_id,)
                ).fetchone()
                self._record_revision(
                    connection,
                    plan_id,
                    source="ui_create",
                    summary=f"Added {block} › {group_name} / {category_name}",
                    change_count=1,
                    when=now,
                )
        except sqlite3.IntegrityError as error:
            if "UNIQUE" in str(error):
                raise DataIntegrityError(
                    f"Category '{group_name} / {category_name}' already exists in plan {plan_id}."
                ) from error
            raise DataIntegrityError(str(error)) from error

        return _row_to_dict(row)

    def update_category(
        self,
        plan_id: int,
        category_id: int,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        for key in EDITABLE_FIELDS:
            if key not in fields:
                continue
            if key in {"planned_milliunits", "annual_target_milliunits"}:
                updates[key] = _coerce_milliunits(fields[key], key)
            elif key == "due_month":
                updates[key] = _coerce_due_month(fields[key])
            elif key == "notes":
                updates[key] = None if fields[key] is None else str(fields[key])
        if not updates:
            raise DataIntegrityError(
                f"No editable fields supplied. Editable: {sorted(EDITABLE_FIELDS)}."
            )

        now = utc_now()
        set_clause = ", ".join(f"{key} = ?" for key in updates) + ", updated_at = ?"
        params: list[Any] = [*updates.values(), now, plan_id, category_id]

        with self.database.connect() as connection:
            self._ensure_plan_exists(connection, plan_id)
            before = connection.execute(
                "SELECT * FROM plan_categories WHERE plan_id = ? AND id = ?",
                (plan_id, category_id),
            ).fetchone()
            if before is None:
                raise NotFoundError(
                    f"Category {category_id} not found in plan {plan_id}."
                )
            connection.execute(
                f"""
                UPDATE plan_categories
                SET {set_clause}
                WHERE plan_id = ? AND id = ?
                """,
                params,
            )
            self._touch_plan(connection, plan_id, now)
            row = connection.execute(
                "SELECT * FROM plan_categories WHERE id = ?", (category_id,)
            ).fetchone()
            self._record_revision(
                connection,
                plan_id,
                source="ui_update",
                summary=_summary_for_update(before, updates),
                change_count=1,
                when=now,
            )

        return _row_to_dict(row)

    def delete_category(self, plan_id: int, category_id: int) -> None:
        now = utc_now()
        with self.database.connect() as connection:
            self._ensure_plan_exists(connection, plan_id)
            before = connection.execute(
                "SELECT * FROM plan_categories WHERE plan_id = ? AND id = ?",
                (plan_id, category_id),
            ).fetchone()
            if before is None:
                raise NotFoundError(
                    f"Category {category_id} not found in plan {plan_id}."
                )
            connection.execute(
                "DELETE FROM plan_categories WHERE plan_id = ? AND id = ?",
                (plan_id, category_id),
            )
            self._touch_plan(connection, plan_id, now)
            self._record_revision(
                connection,
                plan_id,
                source="ui_delete",
                summary=f"Removed {before['block']} › {before['group_name']} / {before['category_name']}",
                change_count=1,
                when=now,
            )

    def rename_category(
        self,
        plan_id: int,
        category_id: int,
        new_group_name: str,
        new_category_name: str,
    ) -> dict[str, Any]:
        new_group_name = _strip_required(new_group_name, "group_name")
        new_category_name = _strip_required(new_category_name, "category_name")
        now = utc_now()
        try:
            with self.database.connect() as connection:
                self._ensure_plan_exists(connection, plan_id)
                before = connection.execute(
                    "SELECT * FROM plan_categories WHERE plan_id = ? AND id = ?",
                    (plan_id, category_id),
                ).fetchone()
                if before is None:
                    raise NotFoundError(
                        f"Category {category_id} not found in plan {plan_id}."
                    )
                connection.execute(
                    """
                    UPDATE plan_categories
                    SET group_name = ?, category_name = ?, updated_at = ?
                    WHERE plan_id = ? AND id = ?
                    """,
                    (new_group_name, new_category_name, now, plan_id, category_id),
                )
                self._touch_plan(connection, plan_id, now)
                row = connection.execute(
                    "SELECT * FROM plan_categories WHERE id = ?", (category_id,)
                ).fetchone()
                self._record_revision(
                    connection,
                    plan_id,
                    source="ui_rename",
                    summary=(
                        f"Renamed {before['group_name']} / {before['category_name']} "
                        f"→ {new_group_name} / {new_category_name}"
                    ),
                    change_count=1,
                    when=now,
                )
        except sqlite3.IntegrityError as error:
            if "UNIQUE" in str(error):
                raise DataIntegrityError(
                    f"Cannot rename: '{new_group_name} / {new_category_name}' "
                    f"already exists in plan {plan_id}."
                ) from error
            raise DataIntegrityError(str(error)) from error

        return _row_to_dict(row)

    def list_revisions(self, plan_id: int, limit: int = 50) -> list[dict[str, Any]]:
        """Return revisions for a plan, newest first. Excludes snapshot_json
        for cheap list rendering — use get_revision(id) for the full payload."""
        if limit <= 0:
            raise DataIntegrityError("limit must be a positive integer.")
        with self.database.connect() as connection:
            self._ensure_plan_exists(connection, plan_id)
            rows = connection.execute(
                """
                SELECT id, plan_id, created_at, source, summary, change_count
                FROM plan_revisions
                WHERE plan_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (plan_id, limit),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "plan_id": row["plan_id"],
                "created_at": row["created_at"],
                "source": row["source"],
                "summary": row["summary"],
                "change_count": row["change_count"],
            }
            for row in rows
        ]

    def get_revision(self, revision_id: int) -> dict[str, Any]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM plan_revisions WHERE id = ?", (revision_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError(f"Revision {revision_id} not found.")
        return {
            "id": row["id"],
            "plan_id": row["plan_id"],
            "created_at": row["created_at"],
            "source": row["source"],
            "summary": row["summary"],
            "change_count": row["change_count"],
            "snapshot": json.loads(row["snapshot_json"]),
        }

    def restore_revision(self, revision_id: int) -> dict[str, Any]:
        """Replace the target plan's categories with those from the revision's
        snapshot, then record the restore as its own revision so the timeline
        stays navigable. Returns the restored plan + categories in the same
        shape as get_active_plan()."""
        now = utc_now()
        with self.database.connect() as connection:
            revision = connection.execute(
                "SELECT * FROM plan_revisions WHERE id = ?", (revision_id,)
            ).fetchone()
            if revision is None:
                raise NotFoundError(f"Revision {revision_id} not found.")
            plan_id = int(revision["plan_id"])
            self._ensure_plan_exists(connection, plan_id)
            snapshot = json.loads(revision["snapshot_json"])
            connection.execute(
                "DELETE FROM plan_categories WHERE plan_id = ?", (plan_id,)
            )
            for category in snapshot:
                connection.execute(
                    """
                    INSERT INTO plan_categories(
                        id, plan_id, group_name, category_name, block,
                        planned_milliunits, annual_target_milliunits, due_month,
                        notes, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        category["id"],
                        plan_id,
                        category["group_name"],
                        category["category_name"],
                        category["block"],
                        category["planned_milliunits"],
                        category["annual_target_milliunits"],
                        category["due_month"],
                        category["notes"],
                        category["created_at"],
                        now,
                    ),
                )
            self._touch_plan(connection, plan_id, now)
            self._record_revision(
                connection,
                plan_id,
                source="restore",
                summary=(
                    f"Restored revision {revision_id} "
                    f"({revision['source']}, {len(snapshot)} categories)"
                ),
                change_count=len(snapshot),
                when=now,
            )
        return self.get_active_plan_by_id(plan_id)

    def get_active_plan_by_id(self, plan_id: int) -> dict[str, Any]:
        with self.database.connect() as connection:
            plan_row = connection.execute(
                "SELECT * FROM plans WHERE id = ?", (plan_id,)
            ).fetchone()
            if plan_row is None:
                raise NotFoundError(f"Plan {plan_id} not found.")
            category_rows = connection.execute(
                """
                SELECT * FROM plan_categories
                WHERE plan_id = ?
                ORDER BY group_name, category_name
                """,
                (plan_id,),
            ).fetchall()
        return _shape_plan_payload(plan_row, category_rows)

    @staticmethod
    def _ensure_plan_exists(connection, plan_id: int) -> None:
        row = connection.execute("SELECT id FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"Plan {plan_id} not found.")

    @staticmethod
    def _touch_plan(connection, plan_id: int, when: str) -> None:
        connection.execute(
            "UPDATE plans SET updated_at = ? WHERE id = ?", (when, plan_id)
        )

    @staticmethod
    def _record_revision(
        connection,
        plan_id: int,
        *,
        source: str,
        summary: str | None,
        change_count: int,
        when: str,
    ) -> None:
        if source not in VALID_REVISION_SOURCES:
            raise DataIntegrityError(
                f"Invalid revision source '{source}'. "
                f"Must be one of: {sorted(VALID_REVISION_SOURCES)}."
            )
        snapshot_rows = connection.execute(
            """
            SELECT id, plan_id, group_name, category_name, block,
                   planned_milliunits, annual_target_milliunits,
                   due_month, notes, created_at, updated_at
            FROM plan_categories
            WHERE plan_id = ?
            ORDER BY id
            """,
            (plan_id,),
        ).fetchall()
        snapshot = [_row_to_dict(row) for row in snapshot_rows]
        connection.execute(
            """
            INSERT INTO plan_revisions(
                plan_id, created_at, source, summary, change_count, snapshot_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                when,
                source,
                summary,
                change_count,
                json.dumps(snapshot, sort_keys=True),
            ),
        )
        _prune_revisions(connection, plan_id)


def _prune_revisions(connection, plan_id: int) -> None:
    """Keep the last RETENTION_KEEP_RECENT revisions per plan, plus anything
    newer than RETENTION_KEEP_DAYS, whichever set is larger."""
    connection.execute(
        f"""
        DELETE FROM plan_revisions
        WHERE plan_id = ?
          AND id NOT IN (
            SELECT id FROM plan_revisions
            WHERE plan_id = ?
              AND created_at >= datetime('now', '-{RETENTION_KEEP_DAYS} days')
          )
          AND id NOT IN (
            SELECT id FROM plan_revisions
            WHERE plan_id = ?
            ORDER BY id DESC
            LIMIT {RETENTION_KEEP_RECENT}
          )
        """,
        (plan_id, plan_id, plan_id),
    )


def _summary_for_update(before, updates: dict[str, Any]) -> str:
    """Render a short, human-readable summary for ui_update revisions."""
    label = f"{before['block']} › {before['group_name']} / {before['category_name']}"
    parts: list[str] = []
    for key, new_value in updates.items():
        old_value = before[key]
        if key in {"planned_milliunits", "annual_target_milliunits"}:
            old_dollars = (old_value or 0) / 1000
            new_dollars = (new_value or 0) / 1000
            short = "planned" if key == "planned_milliunits" else "annual"
            parts.append(f"{short} ${old_dollars:,.2f} → ${new_dollars:,.2f}")
        elif key == "due_month":
            parts.append(f"due_month {old_value!r} → {new_value!r}")
        elif key == "notes":
            parts.append("notes updated")
    if not parts:
        return f"Updated {label}"
    return f"{label}: {', '.join(parts)}"


def _shape_plan_payload(plan_row, category_rows) -> dict[str, Any]:
    blocks: dict[str, list[dict[str, Any]]] = {block: [] for block in VALID_BLOCKS}
    totals: dict[str, int] = {f"{block}_milliunits": 0 for block in VALID_BLOCKS}
    grand_total = 0
    for row in category_rows:
        payload = _row_to_dict(row)
        blocks[payload["block"]].append(payload)
        totals[f"{payload['block']}_milliunits"] += int(payload["planned_milliunits"])
        grand_total += int(payload["planned_milliunits"])
    totals["grand_total_milliunits"] = grand_total
    return {
        "plan": {
            "id": plan_row["id"],
            "plan_year": plan_row["plan_year"],
            "name": plan_row["name"],
            "status": plan_row["status"],
            "source": plan_row["source"],
            "created_at": plan_row["created_at"],
            "updated_at": plan_row["updated_at"],
            "archived_at": plan_row["archived_at"],
            "source_import_id": plan_row["source_import_id"],
        },
        "blocks": blocks,
        "totals": totals,
    }


def _row_to_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "plan_id": row["plan_id"],
        "group_name": row["group_name"],
        "category_name": row["category_name"],
        "block": row["block"],
        "planned_milliunits": row["planned_milliunits"],
        "annual_target_milliunits": row["annual_target_milliunits"],
        "due_month": row["due_month"],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _required_text(fields: dict[str, Any], key: str) -> str:
    value = fields.get(key)
    if value is None:
        raise DataIntegrityError(f"Missing required field '{key}'.")
    return _strip_required(value, key)


def _strip_required(value: Any, key: str) -> str:
    text = str(value).strip()
    if not text:
        raise DataIntegrityError(f"Field '{key}' must not be empty.")
    return text


def _coerce_milliunits(value: Any, key: str) -> int:
    try:
        coerced = int(value)
    except (TypeError, ValueError) as error:
        raise DataIntegrityError(f"Field '{key}' must be an integer milliunits value.") from error
    if coerced < 0:
        raise DataIntegrityError(f"Field '{key}' must be non-negative.")
    return coerced


def _coerce_due_month(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        coerced = int(value)
    except (TypeError, ValueError) as error:
        raise DataIntegrityError("Field 'due_month' must be an integer 1-12 or null.") from error
    if coerced < 1 or coerced > 12:
        raise DataIntegrityError("Field 'due_month' must be between 1 and 12.")
    return coerced
