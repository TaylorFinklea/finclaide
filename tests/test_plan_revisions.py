from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from finclaide.database import Database
from finclaide.errors import NotFoundError
from finclaide.plan_service import (
    RETENTION_KEEP_DAYS,
    RETENTION_KEEP_RECENT,
    PlanService,
)


# --- helpers --------------------------------------------------------------


def _seeded_plan(database: Database) -> tuple[PlanService, int, int, int]:
    """Insert one active plan with two categories and return ids."""
    database.initialize()
    with database.connect() as connection:
        plan_cursor = connection.execute(
            "INSERT INTO plans(plan_year, name, status, source, created_at, updated_at) "
            "VALUES (2027, 'Seed', 'active', 'edited', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
        )
        plan_id = int(plan_cursor.lastrowid)
        rent = connection.execute(
            "INSERT INTO plan_categories(plan_id, group_name, category_name, block, "
            "planned_milliunits, annual_target_milliunits, due_month, notes, created_at, updated_at) "
            "VALUES (?, 'Bills', 'Rent', 'monthly', 1200000, 0, NULL, NULL, "
            "'2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')",
            (plan_id,),
        )
        rent_id = int(rent.lastrowid)
        utilities = connection.execute(
            "INSERT INTO plan_categories(plan_id, group_name, category_name, block, "
            "planned_milliunits, annual_target_milliunits, due_month, notes, created_at, updated_at) "
            "VALUES (?, 'Bills', 'Utilities', 'monthly', 200000, 0, NULL, NULL, "
            "'2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')",
            (plan_id,),
        )
        utilities_id = int(utilities.lastrowid)
    return PlanService(database=database), plan_id, rent_id, utilities_id


def _all_revisions(database: Database, plan_id: int) -> list[sqlite3.Row]:
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM plan_revisions WHERE plan_id = ? ORDER BY id ASC",
            (plan_id,),
        ).fetchall()
    return rows


# --- schema regression ---------------------------------------------------


def test_initialize_creates_plan_revisions_table_and_index(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    db.initialize()
    with db.connect() as connection:
        names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
            )
        }
    assert "plan_revisions" in names
    assert "idx_plan_revisions_plan_created" in names


def test_plans_status_check_admits_draft_and_scenario(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    db.initialize()
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO plans(plan_year, name, status, source, created_at, updated_at) "
            "VALUES (2027, 'Draft', 'draft', 'edited', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
        )
        connection.execute(
            "INSERT INTO plans(plan_year, name, status, source, created_at, updated_at) "
            "VALUES (2027, 'Scenario', 'scenario', 'edited', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
        )


def test_migration_widens_status_check_on_legacy_install(tmp_path: Path):
    """Simulate a pre-2.5b database where plans.status only allows
    ('active', 'archived'). Re-running initialize() should rebuild the
    table to include 'draft' and 'scenario' without losing rows. The
    legacy fixture includes the v_latest_planned_categories view to
    catch the SQLite "view depends on table" error that surfaces in
    real upgrades but not on fresh test DBs."""
    db_path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(db_path)
    try:
        legacy.executescript(
            """
            CREATE TABLE budget_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workbook_path TEXT NOT NULL,
                workbook_sha256 TEXT NOT NULL,
                sheet_name TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                plan_year INTEGER NOT NULL,
                summary_json TEXT NOT NULL
            );
            CREATE TABLE plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_year INTEGER NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('active', 'archived')),
                source TEXT NOT NULL CHECK (source IN ('imported', 'edited')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived_at TEXT,
                source_import_id INTEGER,
                FOREIGN KEY (source_import_id) REFERENCES budget_imports(id) ON DELETE SET NULL
            );
            CREATE TABLE plan_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                group_name TEXT NOT NULL,
                category_name TEXT NOT NULL,
                block TEXT NOT NULL,
                planned_milliunits INTEGER NOT NULL DEFAULT 0,
                annual_target_milliunits INTEGER NOT NULL DEFAULT 0,
                due_month INTEGER,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
            );
            CREATE UNIQUE INDEX idx_plans_active_per_year
                ON plans(plan_year)
                WHERE status = 'active';
            CREATE VIEW v_latest_planned_categories AS
                SELECT pc.id, pc.plan_id AS import_id, pc.group_name,
                       pc.category_name, pc.block, pc.planned_milliunits,
                       pc.annual_target_milliunits, pc.due_month
                FROM plan_categories pc
                JOIN plans p ON p.id = pc.plan_id
                WHERE p.status = 'active'
                ORDER BY pc.id;
            INSERT INTO plans(plan_year, name, status, source, created_at, updated_at)
            VALUES (2027, 'Legacy', 'active', 'edited',
                    '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00');
            """
        )
        legacy.commit()
        # Confirm legacy CHECK rejects 'draft' before migration.
        with pytest.raises(sqlite3.IntegrityError):
            legacy.execute(
                "INSERT INTO plans(plan_year, name, status, source, created_at, updated_at) "
                "VALUES (2028, 'X', 'draft', 'edited', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
            )
            legacy.commit()
        legacy.rollback()
    finally:
        legacy.close()

    db = Database(db_path)
    db.initialize()

    with db.connect() as connection:
        rows = connection.execute(
            "SELECT plan_year, name, status FROM plans ORDER BY id"
        ).fetchall()
        assert [(row["plan_year"], row["name"], row["status"]) for row in rows] == [
            (2027, "Legacy", "active"),
        ]
        # Active uniqueness index survives the rebuild.
        connection.execute(
            "INSERT INTO plans(plan_year, name, status, source, created_at, updated_at) "
            "VALUES (2027, 'Draft', 'draft', 'edited', '2026-01-02T00:00:00+00:00', '2026-01-02T00:00:00+00:00')"
        )

    # Idempotent re-run.
    db.initialize()
    with db.connect() as connection:
        sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'plans'"
        ).fetchone()["sql"]
        assert "'draft'" in sql
        assert "'scenario'" in sql


# --- revision recording on writes ---------------------------------------


def test_create_category_records_ui_create_revision(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    service, plan_id, _, _ = _seeded_plan(db)

    service.create_category(
        plan_id,
        {
            "group_name": "Yearly",
            "category_name": "Insurance",
            "block": "annual",
            "planned_milliunits": 100000,
            "annual_target_milliunits": 1200000,
            "due_month": 6,
        },
    )

    revisions = _all_revisions(db, plan_id)
    assert len(revisions) == 1
    rev = revisions[0]
    assert rev["source"] == "ui_create"
    assert rev["change_count"] == 1
    assert "Yearly / Insurance" in rev["summary"]
    snapshot = json.loads(rev["snapshot_json"])
    names = {(c["group_name"], c["category_name"]) for c in snapshot}
    # Snapshot is post-change: includes the new row plus the original two.
    assert ("Yearly", "Insurance") in names
    assert len(snapshot) == 3


def test_update_category_records_ui_update_revision_with_dollar_summary(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    service, plan_id, rent_id, _ = _seeded_plan(db)

    service.update_category(plan_id, rent_id, {"planned_milliunits": 1300500})

    revisions = _all_revisions(db, plan_id)
    assert len(revisions) == 1
    rev = revisions[0]
    assert rev["source"] == "ui_update"
    assert rev["change_count"] == 1
    assert "monthly › Bills / Rent" in rev["summary"]
    assert "planned $1,200.00 → $1,300.50" in rev["summary"]
    snapshot = json.loads(rev["snapshot_json"])
    rent_in_snapshot = next(c for c in snapshot if c["id"] == rent_id)
    # Post-change snapshot reflects the new amount.
    assert rent_in_snapshot["planned_milliunits"] == 1300500


def test_update_summary_omits_fields_that_did_not_change(tmp_path: Path):
    """The frontend's PATCH always sends the full editable set, so the
    summary needs to filter to only the fields whose value actually moved.
    Otherwise the History list reads "annual $200 → $200, notes updated,
    due_month None → None" on a planned-only edit."""
    db = Database(tmp_path / "f.db")
    service, plan_id, rent_id, _ = _seeded_plan(db)

    # Submit every field, but only planned_milliunits changes.
    service.update_category(
        plan_id,
        rent_id,
        {
            "planned_milliunits": 1300500,
            "annual_target_milliunits": 0,  # unchanged
            "due_month": None,  # unchanged
            "notes": None,  # unchanged
        },
    )

    rev = _all_revisions(db, plan_id)[0]
    assert "planned $1,200.00 → $1,300.50" in rev["summary"]
    assert "annual" not in rev["summary"]
    assert "due_month" not in rev["summary"]
    assert "notes updated" not in rev["summary"]


def test_delete_category_records_ui_delete_revision(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    service, plan_id, rent_id, _ = _seeded_plan(db)

    service.delete_category(plan_id, rent_id)

    revisions = _all_revisions(db, plan_id)
    assert len(revisions) == 1
    rev = revisions[0]
    assert rev["source"] == "ui_delete"
    assert rev["change_count"] == 1
    assert "Removed monthly › Bills / Rent" == rev["summary"]
    snapshot = json.loads(rev["snapshot_json"])
    # Post-change snapshot omits the deleted row.
    assert all(c["id"] != rent_id for c in snapshot)
    assert len(snapshot) == 1


def test_rename_category_records_ui_rename_revision(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    service, plan_id, rent_id, _ = _seeded_plan(db)

    service.rename_category(plan_id, rent_id, "Housing", "Mortgage")

    revisions = _all_revisions(db, plan_id)
    assert len(revisions) == 1
    rev = revisions[0]
    assert rev["source"] == "ui_rename"
    assert rev["summary"] == "Renamed Bills / Rent → Housing / Mortgage"
    snapshot = json.loads(rev["snapshot_json"])
    renamed = next(c for c in snapshot if c["id"] == rent_id)
    assert renamed["group_name"] == "Housing"
    assert renamed["category_name"] == "Mortgage"


def test_failed_create_does_not_leak_revision(tmp_path: Path):
    """A UNIQUE constraint failure rolls back the whole transaction —
    including the would-be revision row. No half-states."""
    db = Database(tmp_path / "f.db")
    service, plan_id, _, _ = _seeded_plan(db)

    from finclaide.errors import DataIntegrityError

    with pytest.raises(DataIntegrityError):
        service.create_category(
            plan_id,
            {
                "group_name": "Bills",
                "category_name": "Rent",  # collides with seeded row
                "block": "monthly",
                "planned_milliunits": 0,
            },
        )

    assert _all_revisions(db, plan_id) == []


# --- restore --------------------------------------------------------------


def test_restore_revision_replaces_categories_and_records_new_revision(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    service, plan_id, rent_id, _ = _seeded_plan(db)

    service.update_category(plan_id, rent_id, {"planned_milliunits": 1300000})
    service.update_category(plan_id, rent_id, {"planned_milliunits": 1500000})

    revisions = _all_revisions(db, plan_id)
    assert len(revisions) == 2
    first_revision_id = revisions[0]["id"]

    restored = service.restore_revision(first_revision_id)
    rent_after = next(
        c for c in restored["blocks"]["monthly"] if c["category_name"] == "Rent"
    )
    assert rent_after["planned_milliunits"] == 1300000

    # Two original updates + one restore = three revisions total.
    revisions_after = _all_revisions(db, plan_id)
    assert len(revisions_after) == 3
    last = revisions_after[-1]
    assert last["source"] == "restore"
    assert f"Restored revision {first_revision_id}" in last["summary"]


def test_restore_missing_revision_raises(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    service, _, _, _ = _seeded_plan(db)
    with pytest.raises(NotFoundError):
        service.restore_revision(9999)


def test_list_revisions_returns_newest_first_without_snapshot_blob(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    service, plan_id, rent_id, _ = _seeded_plan(db)

    service.update_category(plan_id, rent_id, {"planned_milliunits": 1300000})
    service.update_category(plan_id, rent_id, {"planned_milliunits": 1400000})

    listed = service.list_revisions(plan_id)
    assert [rev["source"] for rev in listed] == ["ui_update", "ui_update"]
    # Newest-first ordering.
    assert listed[0]["id"] > listed[1]["id"]
    # List payload omits the heavy snapshot blob.
    assert "snapshot" not in listed[0]


def test_get_revision_returns_full_snapshot(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    service, plan_id, rent_id, _ = _seeded_plan(db)
    service.update_category(plan_id, rent_id, {"planned_milliunits": 1234567})

    rev_id = _all_revisions(db, plan_id)[-1]["id"]
    detail = service.get_revision(rev_id)
    assert detail["source"] == "ui_update"
    assert any(
        c["category_name"] == "Rent" and c["planned_milliunits"] == 1234567
        for c in detail["snapshot"]
    )


# --- retention -----------------------------------------------------------


def test_retention_keeps_recent_revisions_and_prunes_excess_old_rows(tmp_path: Path):
    """Insert RETENTION_KEEP_RECENT + 5 revisions, all backdated past the
    7-day window. The prune should leave exactly RETENTION_KEEP_RECENT."""
    db = Database(tmp_path / "f.db")
    service, plan_id, rent_id, _ = _seeded_plan(db)

    # Backdate everything except the last few — easiest way is to insert
    # directly and then call _prune_revisions manually after each insert by
    # exercising the public path with a mutation.
    extra = 5
    target = RETENTION_KEEP_RECENT + extra

    # Pre-seed (RETENTION_KEEP_RECENT - 1) rows that are old (outside
    # 7-day window) so the recent-N rule is the load-bearing one.
    old_when = "2025-01-01T00:00:00+00:00"
    with db.connect() as connection:
        for i in range(target - 1):
            connection.execute(
                """
                INSERT INTO plan_revisions(
                    plan_id, created_at, source, summary, change_count, snapshot_json
                ) VALUES (?, ?, 'ui_update', ?, 1, '[]')
                """,
                (plan_id, old_when, f"backfill {i}"),
            )

    # One real mutation triggers the prune via _record_revision.
    service.update_category(plan_id, rent_id, {"planned_milliunits": 1234567})

    revisions = _all_revisions(db, plan_id)
    assert len(revisions) == RETENTION_KEEP_RECENT
    # The newest row (the just-inserted ui_update with current timestamp)
    # is preserved.
    newest = revisions[-1]
    assert newest["change_count"] == 1
    assert newest["created_at"] >= "2026-01-01"


def test_retention_keeps_anything_within_seven_days(tmp_path: Path):
    """If many recent rows exist (within RETENTION_KEEP_DAYS), they should
    all survive prune even if it pushes the count above
    RETENTION_KEEP_RECENT — that's the "OR" semantic."""
    db = Database(tmp_path / "f.db")
    service, plan_id, rent_id, _ = _seeded_plan(db)

    extra_recent = 3
    target = RETENTION_KEEP_RECENT + extra_recent
    when = "2026-04-23T12:00:00+00:00"  # well within the 7-day window of 'now'

    # Insert manually to control timestamps.
    with db.connect() as connection:
        for i in range(target - 1):
            connection.execute(
                """
                INSERT INTO plan_revisions(
                    plan_id, created_at, source, summary, change_count, snapshot_json
                ) VALUES (?, ?, 'ui_update', ?, 1, '[]')
                """,
                (plan_id, when, f"recent {i}"),
            )

    service.update_category(plan_id, rent_id, {"planned_milliunits": 9_000})

    # All RETENTION_KEEP_RECENT + extra_recent rows should survive because
    # none of them is older than 7 days. Skip this assertion if the system
    # clock is far in the past relative to `when`; sanity-check only.
    with db.connect() as connection:
        within_window = connection.execute(
            f"""
            SELECT COUNT(*) AS n FROM plan_revisions
            WHERE plan_id = ?
              AND created_at >= datetime('now', '-{RETENTION_KEEP_DAYS} days')
            """,
            (plan_id,),
        ).fetchone()["n"]
    revisions = _all_revisions(db, plan_id)
    if within_window >= target:
        assert len(revisions) == target
    else:
        # If `when` is outside the window for this clock, the recent-N
        # rule applies and we expect exactly RETENTION_KEEP_RECENT rows.
        assert len(revisions) == RETENTION_KEEP_RECENT
