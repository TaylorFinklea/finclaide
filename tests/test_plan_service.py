from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from finclaide.database import Database
from finclaide.errors import DataIntegrityError, NotFoundError
from finclaide.plan_service import PlanService
from tests.workbook_builder import build_budget_workbook


@pytest.fixture
def populated_app(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()
    assert client.post("/api/budget/import", headers=auth_header).status_code == 200
    assert client.post("/api/ynab/sync", headers=auth_header).status_code == 200
    return app


def _plan_service(app) -> PlanService:
    return PlanService(database=app.extensions["finclaide"].database)


# --- schema regression ---------------------------------------------------


def test_initialize_creates_plan_tables_and_view(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    db.initialize()
    with db.connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        assert "plans" in tables
        assert "plan_categories" in tables
        assert "v_latest_planned_categories" in tables

        view_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'v_latest_planned_categories'"
        ).fetchone()["sql"]
        assert "plan_categories" in view_sql
        assert "JOIN plans" in view_sql


def test_active_plan_uniqueness_index_is_enforced_at_db_layer(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    db.initialize()
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO plans(plan_year, name, status, source, created_at, updated_at) "
            "VALUES (2027, 'A', 'active', 'edited', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        with db.connect() as connection:
            connection.execute(
                "INSERT INTO plans(plan_year, name, status, source, created_at, updated_at) "
                "VALUES (2027, 'B', 'active', 'edited', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
            )


def test_archived_plan_does_not_block_new_active(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    db.initialize()
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO plans(plan_year, name, status, source, created_at, updated_at, archived_at) "
            "VALUES (2027, 'A', 'archived', 'edited', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
        )
        connection.execute(
            "INSERT INTO plans(plan_year, name, status, source, created_at, updated_at) "
            "VALUES (2027, 'B', 'active', 'edited', '2026-01-02T00:00:00+00:00', '2026-01-02T00:00:00+00:00')"
        )


# --- hydration ----------------------------------------------------------


def test_initialize_no_hydration_when_no_imports(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    db.initialize()
    with db.connect() as connection:
        count = connection.execute("SELECT COUNT(*) AS n FROM plans").fetchone()["n"]
    assert count == 0


def test_initialize_hydrates_plan_from_latest_import(populated_app, tmp_path: Path):
    services = populated_app.extensions["finclaide"]
    db_path = services.database.db_path

    fresh_db_path = tmp_path / "hydrated.db"
    fresh_db_path.write_bytes(db_path.read_bytes())

    with Database(fresh_db_path).connect() as connection:
        connection.execute("DELETE FROM plan_categories")
        connection.execute("DELETE FROM plans")

    rehydrated = Database(fresh_db_path)
    rehydrated.initialize()

    with rehydrated.connect() as connection:
        plan_count = connection.execute("SELECT COUNT(*) AS n FROM plans").fetchone()["n"]
        category_count = connection.execute(
            "SELECT COUNT(*) AS n FROM plan_categories"
        ).fetchone()["n"]
    assert plan_count == 1
    assert category_count > 0


def test_initialize_hydration_is_idempotent(populated_app):
    db = populated_app.extensions["finclaide"].database
    with db.connect() as connection:
        before = connection.execute("SELECT COUNT(*) AS n FROM plans").fetchone()["n"]
    db.initialize()
    db.initialize()
    with db.connect() as connection:
        after = connection.execute("SELECT COUNT(*) AS n FROM plans").fetchone()["n"]
    assert before == after


# --- importer integration -----------------------------------------------


def test_import_budget_creates_active_plan(populated_app):
    db = populated_app.extensions["finclaide"].database
    with db.connect() as connection:
        plan = connection.execute(
            "SELECT * FROM plans WHERE status = 'active'"
        ).fetchone()
        category_count = connection.execute(
            "SELECT COUNT(*) AS n FROM plan_categories WHERE plan_id = ?",
            (plan["id"],),
        ).fetchone()["n"]
    assert plan is not None
    assert plan["source"] == "imported"
    assert plan["plan_year"] == 2026
    assert category_count == 11


def test_repeated_import_archives_prior_plan(populated_app, auth_header):
    client = populated_app.test_client()
    second = client.post("/api/budget/import", headers=auth_header)
    assert second.status_code == 200

    db = populated_app.extensions["finclaide"].database
    with db.connect() as connection:
        plans = connection.execute(
            "SELECT status, COUNT(*) AS n FROM plans WHERE plan_year = 2026 GROUP BY status"
        ).fetchall()
    counts = {row["status"]: row["n"] for row in plans}
    assert counts.get("active", 0) == 1
    assert counts.get("archived", 0) == 1


def test_view_returns_categories_from_active_plan_only(populated_app):
    db = populated_app.extensions["finclaide"].database
    with db.connect() as connection:
        active_plan_id = connection.execute(
            "SELECT id FROM plans WHERE status = 'active'"
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO plans(plan_year, name, status, source, created_at, updated_at, archived_at) "
            "VALUES (2025, 'Old', 'archived', 'imported', '2025-01-01T00:00:00+00:00', '2025-01-01T00:00:00+00:00', '2025-01-01T00:00:00+00:00')"
        )
        archived_id = connection.execute(
            "SELECT id FROM plans WHERE status = 'archived' AND plan_year = 2025"
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO plan_categories(plan_id, group_name, category_name, block, "
            "planned_milliunits, annual_target_milliunits, due_month, notes, created_at, updated_at) "
            "VALUES (?, 'Bills', 'GhostFromOldPlan', 'monthly', 0, 0, NULL, NULL, "
            "'2025-01-01T00:00:00+00:00', '2025-01-01T00:00:00+00:00')",
            (archived_id,),
        )
        names = {
            row["category_name"]
            for row in connection.execute(
                "SELECT category_name FROM v_latest_planned_categories"
            )
        }
        active_names = {
            row["category_name"]
            for row in connection.execute(
                "SELECT category_name FROM plan_categories WHERE plan_id = ?",
                (active_plan_id,),
            )
        }
    assert "GhostFromOldPlan" not in names
    assert names == active_names


# --- PlanService CRUD ----------------------------------------------------


def test_get_active_plan_groups_by_block(populated_app):
    payload = _plan_service(populated_app).get_active_plan(plan_year=2026)
    assert payload["plan"]["plan_year"] == 2026
    blocks = payload["blocks"]
    assert set(blocks) == {"monthly", "annual", "one_time", "stipends", "savings"}
    assert len(blocks["monthly"]) >= 1
    assert any(c["category_name"] == "Rent" for c in blocks["monthly"])
    assert payload["totals"]["grand_total_milliunits"] > 0


def test_get_active_plan_raises_not_found_when_no_active(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    db.initialize()
    with pytest.raises(NotFoundError):
        PlanService(database=db).get_active_plan()


def test_create_category_inserts_and_appears_in_view(populated_app):
    service = _plan_service(populated_app)
    plan = service.get_active_plan()
    plan_id = plan["plan"]["id"]
    created = service.create_category(
        plan_id,
        {
            "group_name": "Bills",
            "category_name": "Streaming",
            "block": "monthly",
            "planned_milliunits": 25000,
        },
    )
    assert created["category_name"] == "Streaming"
    assert created["planned_milliunits"] == 25000

    db = populated_app.extensions["finclaide"].database
    with db.connect() as connection:
        names = {
            row["category_name"]
            for row in connection.execute(
                "SELECT category_name FROM v_latest_planned_categories"
            )
        }
    assert "Streaming" in names


def test_create_category_rejects_duplicate(populated_app):
    service = _plan_service(populated_app)
    plan_id = service.get_active_plan()["plan"]["id"]
    fields = {
        "group_name": "Bills",
        "category_name": "Streaming",
        "block": "monthly",
        "planned_milliunits": 25000,
    }
    service.create_category(plan_id, fields)
    with pytest.raises(DataIntegrityError, match="already exists"):
        service.create_category(plan_id, fields)


def test_create_category_rejects_invalid_block(populated_app):
    service = _plan_service(populated_app)
    plan_id = service.get_active_plan()["plan"]["id"]
    with pytest.raises(DataIntegrityError, match="Invalid block"):
        service.create_category(
            plan_id,
            {"group_name": "Bills", "category_name": "Phone", "block": "quarterly"},
        )


def test_create_category_rejects_empty_names(populated_app):
    service = _plan_service(populated_app)
    plan_id = service.get_active_plan()["plan"]["id"]
    with pytest.raises(DataIntegrityError, match="must not be empty"):
        service.create_category(
            plan_id,
            {"group_name": "  ", "category_name": "Phone", "block": "monthly"},
        )


def test_update_category_only_modifies_whitelisted_fields(populated_app):
    service = _plan_service(populated_app)
    plan = service.get_active_plan()
    plan_id = plan["plan"]["id"]
    target = plan["blocks"]["monthly"][0]
    original_group = target["group_name"]
    original_category = target["category_name"]
    updated = service.update_category(
        plan_id,
        target["id"],
        {
            "planned_milliunits": 999000,
            "notes": "tweaked",
            "group_name": "HACK",
            "category_name": "HACK",
        },
    )
    assert updated["planned_milliunits"] == 999000
    assert updated["notes"] == "tweaked"
    assert updated["group_name"] == original_group
    assert updated["category_name"] == original_category


def test_update_category_raises_not_found(populated_app):
    service = _plan_service(populated_app)
    plan_id = service.get_active_plan()["plan"]["id"]
    with pytest.raises(NotFoundError):
        service.update_category(plan_id, 99999, {"planned_milliunits": 1})


def test_update_category_rejects_negative_planned(populated_app):
    service = _plan_service(populated_app)
    plan = service.get_active_plan()
    target = plan["blocks"]["monthly"][0]
    with pytest.raises(DataIntegrityError, match="non-negative"):
        service.update_category(plan["plan"]["id"], target["id"], {"planned_milliunits": -1})


def test_delete_category_removes_row_and_view_updates(populated_app):
    service = _plan_service(populated_app)
    plan = service.get_active_plan()
    plan_id = plan["plan"]["id"]
    target = plan["blocks"]["monthly"][0]
    service.delete_category(plan_id, target["id"])
    with pytest.raises(NotFoundError):
        service.delete_category(plan_id, target["id"])

    db = populated_app.extensions["finclaide"].database
    with db.connect() as connection:
        names = {
            row["category_name"]
            for row in connection.execute(
                "SELECT category_name FROM v_latest_planned_categories"
            )
        }
    assert target["category_name"] not in names


def test_rename_category_uniqueness_check(populated_app):
    service = _plan_service(populated_app)
    plan = service.get_active_plan()
    plan_id = plan["plan"]["id"]
    monthly = plan["blocks"]["monthly"]
    src, other = monthly[0], monthly[1]
    with pytest.raises(DataIntegrityError, match="already exists"):
        service.rename_category(
            plan_id,
            src["id"],
            other["group_name"],
            other["category_name"],
        )


def test_existing_consumers_still_work_after_edits(populated_app, auth_header):
    service = _plan_service(populated_app)
    plan = service.get_active_plan()
    plan_id = plan["plan"]["id"]
    target = next(c for c in plan["blocks"]["monthly"] if c["category_name"] == "Rent")
    service.update_category(plan_id, target["id"], {"planned_milliunits": 1500000})

    client = populated_app.test_client()
    summary = client.get("/api/reports/summary?month=2026-03", headers=auth_header).get_json()
    bills = next(group for group in summary["groups"] if group["group_name"] == "Bills")
    rent = next(c for c in bills["categories"] if c["category_name"] == "Rent")
    assert rent["planned_milliunits"] == 1500000


def test_editor_writes_during_busy_import_do_not_deadlock(populated_app):
    services = populated_app.extensions["finclaide"]
    plan_id = _plan_service(populated_app).get_active_plan()["plan"]["id"]
    with services.operation_lock.guard("budget_import"):
        result = _plan_service(populated_app).create_category(
            plan_id,
            {
                "group_name": "Bills",
                "category_name": "Phone",
                "block": "monthly",
                "planned_milliunits": 5000,
            },
        )
    assert result["category_name"] == "Phone"


# --- inflow/outflow kind ------------------------------------------------


def test_create_category_defaults_kind_to_outflow(populated_app):
    service = _plan_service(populated_app)
    plan_id = service.get_active_plan()["plan"]["id"]
    created = service.create_category(
        plan_id,
        {
            "group_name": "Bills",
            "category_name": "Streaming",
            "block": "monthly",
            "planned_milliunits": 25000,
        },
    )
    assert created["kind"] == "outflow"


def test_create_category_with_kind_inflow_round_trips(populated_app):
    service = _plan_service(populated_app)
    plan_id = service.get_active_plan()["plan"]["id"]
    created = service.create_category(
        plan_id,
        {
            "group_name": "Monthly Income",
            "category_name": "Side gig",
            "block": "monthly",
            "planned_milliunits": 200000,
            "kind": "inflow",
        },
    )
    assert created["kind"] == "inflow"
    plan = service.get_active_plan()
    fetched = next(
        c for c in plan["blocks"]["monthly"] if c["category_name"] == "Side gig"
    )
    assert fetched["kind"] == "inflow"


def test_create_category_rejects_invalid_kind(populated_app):
    service = _plan_service(populated_app)
    plan_id = service.get_active_plan()["plan"]["id"]
    with pytest.raises(DataIntegrityError, match="kind"):
        service.create_category(
            plan_id,
            {
                "group_name": "Bills",
                "category_name": "Bad",
                "block": "monthly",
                "kind": "neither",
            },
        )


def test_update_category_can_flip_kind(populated_app):
    service = _plan_service(populated_app)
    plan = service.get_active_plan()
    plan_id = plan["plan"]["id"]
    target = plan["blocks"]["monthly"][0]
    assert target["kind"] == "outflow"
    updated = service.update_category(plan_id, target["id"], {"kind": "inflow"})
    assert updated["kind"] == "inflow"
    flipped_back = service.update_category(plan_id, target["id"], {"kind": "outflow"})
    assert flipped_back["kind"] == "outflow"


def test_kind_migration_backfills_income_groups(tmp_path: Path):
    """A pre-2.5* database (no `kind` column) should gain the column on
    Database.initialize() with rows in 'Monthly Income' / 'Yearly Income'
    groups backfilled to 'inflow' and everything else 'outflow'."""
    db_path = tmp_path / "pre_migration.db"
    # Build a plan_categories table without `kind` to mirror the older schema.
    raw = sqlite3.connect(db_path)
    raw.executescript(
        """
        CREATE TABLE plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_year INTEGER NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            source TEXT NOT NULL,
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
        INSERT INTO plans VALUES (1, 2026, 'Test', 'active', 'imported',
                                  '2026-01-01', '2026-01-01', NULL, NULL);
        INSERT INTO plan_categories
            (plan_id, group_name, category_name, block,
             planned_milliunits, annual_target_milliunits, due_month, notes,
             created_at, updated_at)
        VALUES
            (1, 'Monthly Income', 'Salary',  'monthly',  300000, 0, NULL, NULL,
             '2026-01-01', '2026-01-01'),
            (1, 'Yearly Income',  'Bonus',   'one_time', 100000, 0, NULL, NULL,
             '2026-01-01', '2026-01-01'),
            (1, 'Bills',          'Rent',    'monthly',  100000, 0, NULL, NULL,
             '2026-01-01', '2026-01-01'),
            (1, 'Stipends',       'Lunch',   'stipends',   5000, 0, NULL, NULL,
             '2026-01-01', '2026-01-01');
        """
    )
    raw.commit()
    raw.close()

    Database(db_path).initialize()

    raw = sqlite3.connect(db_path)
    raw.row_factory = sqlite3.Row
    rows = {
        row["category_name"]: row["kind"]
        for row in raw.execute(
            "SELECT category_name, kind FROM plan_categories"
        )
    }
    raw.close()
    assert rows["Salary"] == "inflow"
    assert rows["Bonus"] == "inflow"
    assert rows["Rent"] == "outflow"
    assert rows["Lunch"] == "outflow"


def test_setting_tithe_percent_recomputes_planned(populated_app):
    """Setting `tithe_percent` on a row links its planned_milliunits to the
    current total inflow. The planned amount snaps to the computed value as
    soon as the percent is set."""
    service = _plan_service(populated_app)
    plan = service.get_active_plan()
    plan_id = plan["plan"]["id"]
    inflow = service.create_category(
        plan_id,
        {
            "group_name": "Monthly Income",
            "category_name": "Salary",
            "block": "monthly",
            "planned_milliunits": 1000000,  # $1,000
            "kind": "inflow",
        },
    )
    target = next(c for c in plan["blocks"]["monthly"] if c["category_name"] != "Rent")
    # Pick any outflow row and link it to 10% of inflow.
    target = plan["blocks"]["monthly"][0]
    updated = service.update_category(
        plan_id, target["id"], {"tithe_percent": 10.0}
    )
    assert updated["tithe_percent"] == 10.0
    assert updated["planned_milliunits"] == 100000  # 10% of $1,000


def test_inflow_change_recomputes_all_tithe_rows(populated_app):
    """Updating any inflow row's planned_milliunits should refresh every
    row that has a tithe_percent set."""
    service = _plan_service(populated_app)
    plan = service.get_active_plan()
    plan_id = plan["plan"]["id"]
    inflow = service.create_category(
        plan_id,
        {
            "group_name": "Monthly Income",
            "category_name": "Salary",
            "block": "monthly",
            "planned_milliunits": 1000000,
            "kind": "inflow",
        },
    )
    target = plan["blocks"]["monthly"][0]
    service.update_category(plan_id, target["id"], {"tithe_percent": 10.0})
    # Bump the inflow.
    service.update_category(plan_id, inflow["id"], {"planned_milliunits": 2000000})
    refreshed = service.get_active_plan()
    flipped = next(
        c for c in refreshed["blocks"]["monthly"] if c["id"] == target["id"]
    )
    assert flipped["planned_milliunits"] == 200000  # 10% of $2,000


def test_clearing_tithe_percent_freezes_planned_value(populated_app):
    """Setting tithe_percent back to None should stop auto-recomputing —
    subsequent inflow changes leave the row's planned_milliunits alone."""
    service = _plan_service(populated_app)
    plan = service.get_active_plan()
    plan_id = plan["plan"]["id"]
    inflow = service.create_category(
        plan_id,
        {
            "group_name": "Monthly Income",
            "category_name": "Salary",
            "block": "monthly",
            "planned_milliunits": 1000000,
            "kind": "inflow",
        },
    )
    target = plan["blocks"]["monthly"][0]
    service.update_category(plan_id, target["id"], {"tithe_percent": 10.0})
    # Clear the link; planned should be preserved.
    service.update_category(plan_id, target["id"], {"tithe_percent": None})
    # Now bump inflow — target should NOT auto-update.
    service.update_category(plan_id, inflow["id"], {"planned_milliunits": 2000000})
    final = service.get_active_plan()
    frozen = next(c for c in final["blocks"]["monthly"] if c["id"] == target["id"])
    assert frozen["tithe_percent"] is None
    assert frozen["planned_milliunits"] == 100000  # last computed value, not 200000


def test_deleting_inflow_recomputes_tithes(populated_app):
    service = _plan_service(populated_app)
    plan = service.get_active_plan()
    plan_id = plan["plan"]["id"]
    inflow = service.create_category(
        plan_id,
        {
            "group_name": "Monthly Income",
            "category_name": "Salary",
            "block": "monthly",
            "planned_milliunits": 1000000,
            "kind": "inflow",
        },
    )
    target = plan["blocks"]["monthly"][0]
    service.update_category(plan_id, target["id"], {"tithe_percent": 10.0})
    service.delete_category(plan_id, inflow["id"])
    final = service.get_active_plan()
    rezeroed = next(c for c in final["blocks"]["monthly"] if c["id"] == target["id"])
    assert rezeroed["planned_milliunits"] == 0  # no inflow → 10% of $0 = $0


def test_tithe_only_tithes_same_block_inflows(populated_app):
    """A tithe row computes from inflows IN ITS OWN BLOCK only — irregular
    yearly income (block=one_time) should not affect a monthly tithe. The
    user tithes monthly paychecks here; yearly inflows are tithed manually
    when they actually arrive."""
    service = _plan_service(populated_app)
    plan = service.get_active_plan()
    plan_id = plan["plan"]["id"]
    # Monthly inflow (paycheck-like).
    monthly_inflow = service.create_category(
        plan_id,
        {
            "group_name": "Monthly Income",
            "category_name": "Salary",
            "block": "monthly",
            "planned_milliunits": 1000000,  # $1,000
            "kind": "inflow",
        },
    )
    # One-time inflow (yearly income, e.g. tax refund).
    yearly_inflow = service.create_category(
        plan_id,
        {
            "group_name": "Yearly Income",
            "category_name": "Tax Return",
            "block": "one_time",
            "planned_milliunits": 500000,  # $500/mo equivalent
            "kind": "inflow",
        },
    )
    # Monthly tithe row — should pick up monthly inflow ONLY.
    target = plan["blocks"]["monthly"][0]
    updated = service.update_category(
        plan_id, target["id"], {"tithe_percent": 10.0}
    )
    assert updated["planned_milliunits"] == 100000  # 10% of $1,000 monthly only
    # Bumping the yearly inflow should NOT change the monthly tithe.
    service.update_category(
        plan_id, yearly_inflow["id"], {"planned_milliunits": 5000000}
    )
    refreshed = service.get_active_plan()
    isolated = next(
        c for c in refreshed["blocks"]["monthly"] if c["id"] == target["id"]
    )
    assert isolated["planned_milliunits"] == 100000  # still 10% of monthly inflow


def test_tithe_percent_rejects_out_of_range(populated_app):
    service = _plan_service(populated_app)
    plan = service.get_active_plan()
    plan_id = plan["plan"]["id"]
    target = plan["blocks"]["monthly"][0]
    with pytest.raises(DataIntegrityError, match="tithe_percent"):
        service.update_category(plan_id, target["id"], {"tithe_percent": 150.0})
    with pytest.raises(DataIntegrityError, match="tithe_percent"):
        service.update_category(plan_id, target["id"], {"tithe_percent": -1})


def test_kind_migration_is_idempotent(tmp_path: Path):
    """Running initialize() twice on a freshly-migrated db must not error,
    and must preserve the kind values set by user edits made in between."""
    db = Database(tmp_path / "f.db")
    db.initialize()
    with db.connect() as connection:
        connection.execute(
            """
            INSERT INTO plans(plan_year, name, status, source,
                              created_at, updated_at)
            VALUES (2026, 'Test', 'active', 'imported',
                    '2026-01-01', '2026-01-01')
            """
        )
        plan_id = connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        connection.execute(
            """
            INSERT INTO plan_categories(plan_id, group_name, category_name,
                                        block, kind, planned_milliunits,
                                        annual_target_milliunits, due_month,
                                        notes, created_at, updated_at)
            VALUES (?, 'Bills', 'Manual income', 'monthly', 'inflow',
                    50000, 0, NULL, NULL, '2026-01-01', '2026-01-01')
            """,
            (plan_id,),
        )

    db.initialize()  # second pass — must be a no-op for kind values

    with db.connect() as connection:
        kind = connection.execute(
            "SELECT kind FROM plan_categories WHERE category_name = 'Manual income'"
        ).fetchone()["kind"]
    assert kind == "inflow"
