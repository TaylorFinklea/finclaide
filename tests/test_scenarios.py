from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from finclaide.database import Database
from finclaide.errors import DataIntegrityError, NotFoundError
from finclaide.plan_service import PlanService


# --- helpers --------------------------------------------------------------


def _seeded_active(database: Database) -> tuple[PlanService, int]:
    """Initialize and seed an active plan with two categories. Returns the
    service and the active plan id."""
    database.initialize()
    with database.connect() as connection:
        plan_cursor = connection.execute(
            "INSERT INTO plans(plan_year, name, status, source, created_at, updated_at) "
            "VALUES (2027, 'Seed', 'active', 'edited', "
            "'2026-04-01T00:00:00+00:00', '2026-04-01T00:00:00+00:00')"
        )
        plan_id = int(plan_cursor.lastrowid)
        connection.execute(
            "INSERT INTO plan_categories(plan_id, group_name, category_name, block, "
            "planned_milliunits, annual_target_milliunits, due_month, notes, created_at, updated_at) "
            "VALUES (?, 'Bills', 'Rent', 'monthly', 1200000, 0, NULL, NULL, "
            "'2026-04-01T00:00:00+00:00', '2026-04-01T00:00:00+00:00')",
            (plan_id,),
        )
        connection.execute(
            "INSERT INTO plan_categories(plan_id, group_name, category_name, block, "
            "planned_milliunits, annual_target_milliunits, due_month, notes, created_at, updated_at) "
            "VALUES (?, 'Bills', 'Utilities', 'monthly', 200000, 0, NULL, NULL, "
            "'2026-04-01T00:00:00+00:00', '2026-04-01T00:00:00+00:00')",
            (plan_id,),
        )
    return PlanService(database=database), plan_id


# --- schema ---------------------------------------------------------------


def test_initialize_adds_label_column_and_indexes(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    db.initialize()
    with db.connect() as connection:
        cols = connection.execute("PRAGMA table_info(plans)").fetchall()
        names = connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('index')"
        ).fetchall()
    assert any(col["name"] == "label" for col in cols)
    index_names = {row["name"] for row in names}
    assert "idx_plans_one_sandbox" in index_names
    assert "idx_plans_saved_label_unique" in index_names


def test_label_migration_runs_against_pre_2_5c_install(tmp_path: Path):
    """Simulate an install at 2.5b shape (no label column yet) and verify the
    migration adds it idempotently."""
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_year INTEGER NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('active', 'archived', 'draft', 'scenario')),
            source TEXT NOT NULL CHECK (source IN ('imported', 'edited')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived_at TEXT,
            source_import_id INTEGER
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
            updated_at TEXT NOT NULL
        );
        CREATE VIEW v_latest_planned_categories AS
        SELECT pc.id, pc.plan_id AS import_id, pc.group_name, pc.category_name,
               pc.block, pc.planned_milliunits, pc.annual_target_milliunits,
               pc.due_month, NULL AS formula_text, NULL AS source_cell,
               NULL AS planned_group_id
        FROM plan_categories pc
        JOIN plans p ON p.id = pc.plan_id
        WHERE p.status = 'active';
        INSERT INTO plans(plan_year, name, status, source, created_at, updated_at)
        VALUES (2027, 'Pre-2.5c', 'active', 'edited',
                '2026-04-01T00:00:00+00:00', '2026-04-01T00:00:00+00:00');
        """
    )
    connection.commit()
    connection.close()

    Database(db_path).initialize()
    Database(db_path).initialize()  # second run is a no-op

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    cols = connection.execute("PRAGMA table_info(plans)").fetchall()
    legacy_count = connection.execute(
        "SELECT COUNT(*) AS n FROM plans WHERE name = 'Pre-2.5c'"
    ).fetchone()["n"]
    connection.close()
    assert any(col["name"] == "label" for col in cols)
    assert legacy_count == 1


# --- create_scenario ------------------------------------------------------


def test_create_scenario_with_no_label_creates_sandbox(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    payload = service.create_scenario(plan_id)
    assert payload["plan"]["status"] == "scenario"
    assert payload["plan"]["label"] is None
    # Categories were copied
    rows = payload["blocks"]["monthly"]
    assert {(c["group_name"], c["category_name"]) for c in rows} == {
        ("Bills", "Rent"),
        ("Bills", "Utilities"),
    }


def test_create_scenario_with_label_creates_saved(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    payload = service.create_scenario(plan_id, label="Summer budget")
    assert payload["plan"]["label"] == "Summer budget"


def test_create_second_sandbox_rejected(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    service.create_scenario(plan_id)
    with pytest.raises(DataIntegrityError, match="sandbox already exists"):
        service.create_scenario(plan_id)


def test_create_duplicate_saved_label_rejected(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    service.create_scenario(plan_id, label="Summer budget")
    with pytest.raises(DataIntegrityError, match="Summer budget"):
        service.create_scenario(plan_id, label="Summer budget")


def test_create_saved_alongside_sandbox_works(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    saved = service.create_scenario(plan_id, label="Summer budget")
    assert sandbox["plan"]["label"] is None
    assert saved["plan"]["label"] == "Summer budget"


def test_create_scenario_missing_plan_raises_not_found(tmp_path: Path):
    service, _ = _seeded_active(Database(tmp_path / "f.db"))
    with pytest.raises(NotFoundError):
        service.create_scenario(99999)


# --- list_scenarios -------------------------------------------------------


def test_list_scenarios_returns_only_scenarios_newest_first(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    a = service.create_scenario(plan_id, label="Plan A")
    b = service.create_scenario(plan_id, label="Plan B")
    listed = service.list_scenarios()
    assert [s["id"] for s in listed] == [b["plan"]["id"], a["plan"]["id"]]
    assert all(s["status"] == "scenario" for s in listed)
    assert all(s["category_count"] == 2 for s in listed)


# --- commit_scenario ------------------------------------------------------


def test_commit_scenario_archives_prior_active(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    sandbox_id = sandbox["plan"]["id"]
    result = service.commit_scenario(sandbox_id)
    assert result["plan"]["id"] == sandbox_id
    assert result["plan"]["status"] == "active"
    assert result["plan"]["label"] is None
    with service.database.connect() as connection:
        prior = connection.execute(
            "SELECT status, archived_at FROM plans WHERE id = ?", (plan_id,)
        ).fetchone()
    assert prior["status"] == "archived"
    assert prior["archived_at"] is not None


def test_commit_scenario_records_migration_revision_on_prior_active(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    saved = service.create_scenario(plan_id, label="Summer budget")
    service.commit_scenario(saved["plan"]["id"])
    revisions = service.list_revisions(plan_id)
    assert any(
        rev["source"] == "migration"
        and rev["summary"] == "Replaced by scenario: Summer budget"
        for rev in revisions
    )


def test_commit_sandbox_attribution_uses_sandbox_label(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    service.commit_scenario(sandbox["plan"]["id"])
    revisions = service.list_revisions(plan_id)
    assert any(
        rev["source"] == "migration" and rev["summary"] == "Replaced by sandbox"
        for rev in revisions
    )


def test_commit_records_post_commit_revision_on_new_active(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    sandbox_id = sandbox["plan"]["id"]
    service.commit_scenario(sandbox_id)
    revisions = service.list_revisions(sandbox_id)
    assert any(rev["source"] == "migration" for rev in revisions)


def test_commit_unknown_scenario_raises_not_found(tmp_path: Path):
    service, _ = _seeded_active(Database(tmp_path / "f.db"))
    with pytest.raises(NotFoundError):
        service.commit_scenario(99999)


def test_commit_active_plan_directly_raises_not_found(tmp_path: Path):
    """Cannot commit something that's not a scenario."""
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    with pytest.raises(NotFoundError):
        service.commit_scenario(plan_id)


def test_after_commit_a_new_sandbox_can_be_created(tmp_path: Path):
    """The unique-sandbox index is per-row state, not historical — once the
    sandbox flips to active, a new sandbox can be created against it."""
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    service.commit_scenario(sandbox["plan"]["id"])
    # Original active is archived; sandbox is now active. Create a new
    # sandbox against the new active.
    next_sandbox = service.create_scenario(sandbox["plan"]["id"])
    assert next_sandbox["plan"]["status"] == "scenario"
    assert next_sandbox["plan"]["label"] is None


# --- discard_scenario -----------------------------------------------------


def test_discard_scenario_hard_deletes_with_cascading_categories(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    sandbox_id = sandbox["plan"]["id"]
    service.discard_scenario(sandbox_id)
    with service.database.connect() as connection:
        plan_count = connection.execute(
            "SELECT COUNT(*) AS n FROM plans WHERE id = ?", (sandbox_id,)
        ).fetchone()["n"]
        cat_count = connection.execute(
            "SELECT COUNT(*) AS n FROM plan_categories WHERE plan_id = ?", (sandbox_id,)
        ).fetchone()["n"]
    assert plan_count == 0
    assert cat_count == 0


def test_discard_scenario_does_not_affect_active(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    service.discard_scenario(sandbox["plan"]["id"])
    active = service.get_active_plan_by_id(plan_id)
    assert active["plan"]["status"] == "active"
    assert len(active["blocks"]["monthly"]) == 2


def test_discard_unknown_scenario_raises_not_found(tmp_path: Path):
    service, _ = _seeded_active(Database(tmp_path / "f.db"))
    with pytest.raises(NotFoundError):
        service.discard_scenario(99999)


def test_discard_active_plan_directly_raises_not_found(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    with pytest.raises(NotFoundError):
        service.discard_scenario(plan_id)


# --- edit-on-scenario integration ----------------------------------------


def test_editing_sandbox_creates_revision_tagged_with_sandbox_id(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    sandbox_id = sandbox["plan"]["id"]
    rent = next(c for c in sandbox["blocks"]["monthly"] if c["category_name"] == "Rent")
    service.update_category(sandbox_id, rent["id"], {"planned_milliunits": 1500000})
    sandbox_revisions = service.list_revisions(sandbox_id)
    active_revisions = service.list_revisions(plan_id)
    assert any(rev["source"] == "ui_update" for rev in sandbox_revisions)
    assert all(rev["source"] != "ui_update" for rev in active_revisions)
