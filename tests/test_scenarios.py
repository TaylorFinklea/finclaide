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


# --- save_scenario --------------------------------------------------------


def test_save_scenario_promotes_sandbox_with_label(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    sandbox_id = sandbox["plan"]["id"]
    saved = service.save_scenario(sandbox_id, "Summer budget")
    assert saved["plan"]["id"] == sandbox_id
    assert saved["plan"]["label"] == "Summer budget"
    listed = service.list_scenarios()
    assert any(s["id"] == sandbox_id and s["label"] == "Summer budget" for s in listed)


def test_save_scenario_rejects_blank_label(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    with pytest.raises(DataIntegrityError):
        service.save_scenario(sandbox["plan"]["id"], "   ")


def test_save_scenario_rejects_duplicate_label(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    service.create_scenario(plan_id, label="Summer budget")
    sandbox = service.create_scenario(plan_id)
    with pytest.raises(DataIntegrityError, match="Summer budget"):
        service.save_scenario(sandbox["plan"]["id"], "Summer budget")


def test_save_scenario_idempotent_with_same_label_on_same_id(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    service.save_scenario(sandbox["plan"]["id"], "Summer budget")
    again = service.save_scenario(sandbox["plan"]["id"], "Summer budget")
    assert again["plan"]["label"] == "Summer budget"


def test_save_scenario_unknown_id_raises_not_found(tmp_path: Path):
    service, _ = _seeded_active(Database(tmp_path / "f.db"))
    with pytest.raises(NotFoundError):
        service.save_scenario(99999, "Summer budget")


def test_save_scenario_active_plan_id_raises_not_found(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    with pytest.raises(NotFoundError):
        service.save_scenario(plan_id, "Summer budget")


# --- fork_scenario --------------------------------------------------------


def test_fork_scenario_returns_new_sandbox(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    saved = service.create_scenario(plan_id, label="Summer budget")
    forked = service.fork_scenario(saved["plan"]["id"])
    assert forked["plan"]["id"] != saved["plan"]["id"]
    assert forked["plan"]["status"] == "scenario"
    assert forked["plan"]["label"] is None
    assert forked["plan"]["plan_year"] == saved["plan"]["plan_year"]
    # Categories deep-copied with fresh ids
    forked_cats = forked["blocks"]["monthly"]
    saved_cats = saved["blocks"]["monthly"]
    assert {(c["group_name"], c["category_name"]) for c in forked_cats} == {
        (c["group_name"], c["category_name"]) for c in saved_cats
    }
    assert {c["id"] for c in forked_cats}.isdisjoint({c["id"] for c in saved_cats})


def test_fork_scenario_when_sandbox_exists_raises_data_integrity(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    saved = service.create_scenario(plan_id, label="Summer budget")
    service.create_scenario(plan_id)  # existing sandbox
    with pytest.raises(DataIntegrityError, match="sandbox already exists"):
        service.fork_scenario(saved["plan"]["id"])


def test_fork_scenario_rejects_active_plan(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    with pytest.raises(NotFoundError):
        service.fork_scenario(plan_id)


def test_fork_scenario_rejects_unsaved_sandbox(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    with pytest.raises(NotFoundError):
        service.fork_scenario(sandbox["plan"]["id"])


def test_fork_scenario_unknown_id_raises_not_found(tmp_path: Path):
    service, _ = _seeded_active(Database(tmp_path / "f.db"))
    with pytest.raises(NotFoundError):
        service.fork_scenario(99999)


# --- compare_scenario -----------------------------------------------------


def _seed_transaction(
    database: Database,
    *,
    date: str,
    group_name: str,
    category_name: str,
    amount_milliunits: int,
) -> None:
    """Insert a transaction tagged with a free-form group/category. Uses the
    transactions table directly because the test fixtures don't go through
    YNAB sync. Outflows should pass negative amount_milliunits."""
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO transactions(
                id, plan_id, account_id, date, payee_name, memo,
                cleared, approved, category_id, category_name, group_name,
                amount_milliunits, deleted, raw_json, updated_at
            )
            VALUES (?, 'plan-test', NULL, ?, 'Test', NULL,
                    'cleared', 1, NULL, ?, ?, ?, 0, '{}', ?)
            """,
            (
                f"txn-{date}-{category_name}",
                date,
                category_name,
                group_name,
                amount_milliunits,
                "2026-04-01T00:00:00+00:00",
            ),
        )


def test_compare_scenario_returns_six_month_window(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    response = service.compare_scenario(sandbox["plan"]["id"])
    assert len(response["window"]["months"]) == 6
    assert response["scenario_id"] == sandbox["plan"]["id"]
    assert response["active_id"] == plan_id


def test_compare_scenario_aligns_planned_with_active(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    sandbox_id = sandbox["plan"]["id"]
    rent = next(c for c in sandbox["blocks"]["monthly"] if c["category_name"] == "Rent")
    service.update_category(sandbox_id, rent["id"], {"planned_milliunits": 1500000})
    response = service.compare_scenario(sandbox_id)
    rent_row = next(
        r for r in response["rows"] if r["name"].endswith("Rent")
    )
    assert rent_row["planned_active_milliunits"] == 1200000
    assert rent_row["planned_scenario_milliunits"] == 1500000
    assert rent_row["vs_active_milliunits"] == 300000


def test_compare_scenario_includes_added_in_scenario_only(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    sandbox_id = sandbox["plan"]["id"]
    service.create_category(
        sandbox_id,
        {
            "group_name": "Bills",
            "category_name": "Internet",
            "block": "monthly",
            "planned_milliunits": 75000,
        },
    )
    response = service.compare_scenario(sandbox_id)
    new_row = next(r for r in response["rows"] if r["name"].endswith("Internet"))
    assert new_row["planned_active_milliunits"] == 0
    assert new_row["planned_scenario_milliunits"] == 75000


def test_compare_scenario_includes_deleted_in_scenario_only(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    sandbox_id = sandbox["plan"]["id"]
    utilities = next(
        c for c in sandbox["blocks"]["monthly"] if c["category_name"] == "Utilities"
    )
    service.delete_category(sandbox_id, utilities["id"])
    response = service.compare_scenario(sandbox_id)
    util_row = next(r for r in response["rows"] if r["name"].endswith("Utilities"))
    assert util_row["planned_active_milliunits"] == 200000
    assert util_row["planned_scenario_milliunits"] == 0


def test_compare_scenario_handles_no_transactions(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    response = service.compare_scenario(sandbox["plan"]["id"])
    for row in response["rows"]:
        assert row["sparkline"] == [0, 0, 0, 0, 0, 0]
        assert row["actuals_avg_6mo_milliunits"] == 0


def test_compare_scenario_sparkline_aggregates_transactions(tmp_path: Path):
    db = Database(tmp_path / "f.db")
    service, plan_id = _seeded_active(db)
    sandbox = service.create_scenario(plan_id)

    # Compute the 6 in-window months from today and seed one outflow per
    # month, varying the magnitude so we can assert order. We feed the
    # _n_months_ago helper directly to mirror compare_scenario's window.
    from finclaide.analytics import _month_reference, _n_months_ago

    reference = _month_reference(None)
    months = [_n_months_ago(i, reference) for i in range(6, 0, -1)]
    for index, month in enumerate(months):
        # 100, 200, 300, 400, 500, 600 thousand milliunits respectively.
        amount = -1 * (index + 1) * 100000
        _seed_transaction(
            db,
            date=f"{month}-15",
            group_name="Bills",
            category_name="Rent",
            amount_milliunits=amount,
        )

    response = service.compare_scenario(sandbox["plan"]["id"])
    rent_row = next(r for r in response["rows"] if r["name"].endswith("Rent"))
    assert rent_row["sparkline"] == [100000, 200000, 300000, 400000, 500000, 600000]
    assert rent_row["actuals_avg_6mo_milliunits"] == sum(rent_row["sparkline"]) // 6


def test_compare_scenario_no_active_for_year_raises_data_integrity(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    sandbox_id = sandbox["plan"]["id"]
    # Archive the active so there's no same-year active.
    with service.database.connect() as connection:
        connection.execute(
            "UPDATE plans SET status = 'archived' WHERE id = ?", (plan_id,)
        )
    with pytest.raises(DataIntegrityError, match="No active plan"):
        service.compare_scenario(sandbox_id)


def test_compare_scenario_unknown_id_raises_not_found(tmp_path: Path):
    service, _ = _seeded_active(Database(tmp_path / "f.db"))
    with pytest.raises(NotFoundError):
        service.compare_scenario(99999)


def test_compare_scenario_active_plan_id_raises_not_found(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    with pytest.raises(NotFoundError):
        service.compare_scenario(plan_id)


def test_compare_scenario_totals_match_row_sums(tmp_path: Path):
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    sandbox = service.create_scenario(plan_id)
    sandbox_id = sandbox["plan"]["id"]
    rent = next(c for c in sandbox["blocks"]["monthly"] if c["category_name"] == "Rent")
    service.update_category(sandbox_id, rent["id"], {"planned_milliunits": 1500000})
    response = service.compare_scenario(sandbox_id)
    assert response["totals"]["planned_active_milliunits"] == sum(
        r["planned_active_milliunits"] for r in response["rows"]
    )
    assert response["totals"]["planned_scenario_milliunits"] == sum(
        r["planned_scenario_milliunits"] for r in response["rows"]
    )
    assert response["totals"]["vs_active_milliunits"] == sum(
        r["vs_active_milliunits"] for r in response["rows"]
    )


# --- compare_projection ---------------------------------------------------


def test_compare_projection_applies_axis_percent_delta(tmp_path: Path):
    """Axis with -20% on Rent ($1200) → projected $960."""
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    # Get Rent's category_id from the active plan.
    active = service.get_active_plan_by_id(plan_id)
    rent = next(c for c in active["blocks"]["monthly"] if c["category_name"] == "Rent")
    response = service.compare_projection(
        axes=[{"category_id": rent["id"], "percent_delta": -20}],
        new_lines=[],
    )
    rent_row = next(r for r in response["rows"] if r["name"].endswith("Rent"))
    assert rent_row["planned_active_milliunits"] == 1200000
    assert rent_row["planned_scenario_milliunits"] == 960000
    assert response["scenario_id"] is None
    assert response["active_id"] == plan_id


def test_compare_projection_includes_new_lines_as_virtual_rows(tmp_path: Path):
    """new_line with $50000 milliunits → row with sentinel id < 0 and zero sparkline."""
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    response = service.compare_projection(
        axes=[],
        new_lines=[{"group": "Expenses", "name": "Emergency", "monthly_amount_milliunits": 50000}],
    )
    emerg_row = next(r for r in response["rows"] if r["name"].endswith("Emergency"))
    assert emerg_row["category_id"] == -1
    assert emerg_row["planned_scenario_milliunits"] == 50000
    assert emerg_row["sparkline"] == [0, 0, 0, 0, 0, 0]


def test_compare_projection_no_writes_to_db(tmp_path: Path):
    """compare_projection is pure-read: plan + plan_categories row counts unchanged."""
    db = Database(tmp_path / "f.db")
    service, plan_id = _seeded_active(db)
    active = service.get_active_plan_by_id(plan_id)
    rent = next(c for c in active["blocks"]["monthly"] if c["category_name"] == "Rent")

    with db.connect() as connection:
        plan_count_before = connection.execute("SELECT COUNT(*) AS n FROM plans").fetchone()["n"]
        cat_count_before = connection.execute(
            "SELECT COUNT(*) AS n FROM plan_categories"
        ).fetchone()["n"]

    service.compare_projection(
        axes=[{"category_id": rent["id"], "percent_delta": 10}],
        new_lines=[{"group": "X", "name": "Y", "monthly_amount_milliunits": 1000}],
    )

    with db.connect() as connection:
        plan_count_after = connection.execute("SELECT COUNT(*) AS n FROM plans").fetchone()["n"]
        cat_count_after = connection.execute(
            "SELECT COUNT(*) AS n FROM plan_categories"
        ).fetchone()["n"]

    assert plan_count_before == plan_count_after
    assert cat_count_before == cat_count_after


def test_compare_projection_handles_zero_axes_and_no_new_lines(tmp_path: Path):
    """Empty axes/new_lines → all rows show 0 delta; totals match active sums."""
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    response = service.compare_projection(axes=[], new_lines=[])
    for row in response["rows"]:
        assert row["vs_active_milliunits"] == 0
    assert response["totals"]["vs_active_milliunits"] == 0
    assert response["totals"]["planned_active_milliunits"] == 1400000


def test_compare_projection_handles_unknown_category_id_silently(tmp_path: Path):
    """Axis with non-existent category_id is ignored; no error raised."""
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    response = service.compare_projection(
        axes=[{"category_id": 99999, "percent_delta": 50}],
        new_lines=[],
    )
    # Should still return rows for the two active categories with 0 delta.
    assert len(response["rows"]) == 2
    for row in response["rows"]:
        assert row["vs_active_milliunits"] == 0


# --- apply_projection_to_sandbox ------------------------------------------


def test_apply_projection_creates_sandbox_with_axis_overrides(tmp_path: Path):
    """axes=[(Rent, +10%)] → new sandbox has Rent at $1320000."""
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    active = service.get_active_plan_by_id(plan_id)
    rent = next(c for c in active["blocks"]["monthly"] if c["category_name"] == "Rent")

    result = service.apply_projection_to_sandbox(
        axes=[{"category_id": rent["id"], "percent_delta": 10}],
        new_lines=[],
    )
    assert result["plan"]["status"] == "scenario"
    assert result["plan"]["label"] is None
    sandbox_rent = next(c for c in result["blocks"]["monthly"] if c["category_name"] == "Rent")
    assert sandbox_rent["planned_milliunits"] == 1320000

    # Appears in scenarios list.
    listed = service.list_scenarios()
    assert any(s["id"] == result["plan"]["id"] for s in listed)


def test_apply_projection_with_new_lines_creates_plan_categories(tmp_path: Path):
    """new_lines=[{Expenses, Emergency, $50000}] → sandbox has the new row."""
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    result = service.apply_projection_to_sandbox(
        axes=[],
        new_lines=[{"group": "Expenses", "name": "Emergency", "monthly_amount_milliunits": 50000}],
    )
    all_cats = [c for block in result["blocks"].values() for c in block]
    emerg = next((c for c in all_cats if c["category_name"] == "Emergency"), None)
    assert emerg is not None
    assert emerg["planned_milliunits"] == 50000
    assert emerg["group_name"] == "Expenses"


def test_apply_projection_when_sandbox_exists_raises(tmp_path: Path):
    """Pre-existing sandbox → DataIntegrityError (UI shows auto-park modal)."""
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    service.create_scenario(plan_id)  # creates sandbox
    with pytest.raises(DataIntegrityError, match="sandbox already exists"):
        service.apply_projection_to_sandbox(axes=[], new_lines=[])


def test_apply_projection_writes_revisions(tmp_path: Path):
    """Each axis change generates a ui_update plan_revision on the new sandbox."""
    service, plan_id = _seeded_active(Database(tmp_path / "f.db"))
    active = service.get_active_plan_by_id(plan_id)
    rent = next(c for c in active["blocks"]["monthly"] if c["category_name"] == "Rent")

    result = service.apply_projection_to_sandbox(
        axes=[{"category_id": rent["id"], "percent_delta": 5}],
        new_lines=[],
    )
    sandbox_id = result["plan"]["id"]
    revisions = service.list_revisions(sandbox_id)
    assert any(rev["source"] == "ui_update" for rev in revisions)
