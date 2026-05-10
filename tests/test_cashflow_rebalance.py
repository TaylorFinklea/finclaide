"""Tests for the rebalance prompts that pair calibration recs with a
compensating cushion category, plus standalone deficit prompts when the
operator's hand-edited plan is unbalanced."""
from __future__ import annotations

from pathlib import Path

from finclaide.budget_sheet import BudgetImporter
from finclaide.config import AppConfig
from finclaide.database import Database
from finclaide.analytics import AnalyticsService
from finclaide.locking import OperationLock
from tests.workbook_builder import build_budget_workbook


def _setup(tmp_path: Path) -> tuple[AnalyticsService, Database]:
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    database = Database(tmp_path / "f.db")
    database.initialize()
    BudgetImporter(database).import_budget(workbook, "2026 Budget")
    config = AppConfig(
        api_token="x",
        ynab_access_token=None,
        ynab_plan_id=None,
        db_path=tmp_path / "f.db",
        budget_source="local_file",
        budget_xlsx=workbook,
        budget_xlsx_url=None,
        budget_xlsx_download_path=None,
        google_service_account_path=None,
        google_sheets_file_id=None,
        budget_sheet_name="2026 Budget",
        host="127.0.0.1",
        port=8050,
        scheduled_refresh_enabled=False,
        scheduled_refresh_bootstrap_on_start=False,
        scheduled_refresh_interval_minutes=360,
    )
    return (
        AnalyticsService(
            config=config, database=database, operation_lock=OperationLock()
        ),
        database,
    )


def _add_inflow(
    database: Database, *, name: str, planned_milliunits: int
) -> int:
    """Insert an inflow row and return its category id."""
    with database.connect() as conn:
        plan_id = conn.execute(
            "SELECT id FROM plans WHERE status='active'"
        ).fetchone()["id"]
        cur = conn.execute(
            """
            INSERT INTO plan_categories(
                plan_id, group_name, category_name, block, kind,
                planned_milliunits, annual_target_milliunits, due_month,
                notes, created_at, updated_at
            )
            VALUES (?, 'Monthly Income', ?, 'monthly', 'inflow', ?, 0,
                    NULL, NULL, '2026-05-01', '2026-05-01')
            """,
            (plan_id, name, planned_milliunits),
        )
        return int(cur.lastrowid or 0)


def _set_planned(database: Database, *, category_name: str, milliunits: int) -> int:
    with database.connect() as conn:
        cur = conn.execute(
            """
            UPDATE plan_categories
            SET planned_milliunits = ?
            WHERE category_name = ?
              AND plan_id = (SELECT id FROM plans WHERE status='active')
            """,
            (milliunits, category_name),
        )
        row = conn.execute(
            """
            SELECT id FROM plan_categories
            WHERE category_name = ?
              AND plan_id = (SELECT id FROM plans WHERE status='active')
            """,
            (category_name,),
        ).fetchone()
        if cur.rowcount == 0:
            raise AssertionError(f"No row named {category_name!r}")
        return int(row["id"])


def _seed_overrun(
    database: Database, *, group: str, category: str, monthly_milliunits: int
) -> None:
    months = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]
    with database.connect() as conn:
        for i, m in enumerate(months):
            conn.execute(
                """
                INSERT INTO transactions(
                    id, plan_id, account_id, date, payee_name, memo, cleared,
                    approved, category_id, category_name, group_name,
                    amount_milliunits, deleted, raw_json, updated_at
                ) VALUES (?, 'plan-test', 'acct-1', ?, 'Test', NULL, 'cleared',
                          1, NULL, ?, ?, ?, 0, '{}', '2026-04-30T00:00:00+00:00')
                """,
                (
                    f"t-{group}-{category}-{i}",
                    f"{m}-15",
                    category,
                    group,
                    -abs(monthly_milliunits),
                ),
            )


# --- tests ----------------------------------------------------------------


def test_no_prompt_when_cascade_already_positive_and_no_recs(tmp_path: Path):
    """Empty path: operator's plan already balances and there's no
    overrun to surface — nothing to suggest."""
    service, database = _setup(tmp_path)
    _add_inflow(database, name="Salary", planned_milliunits=10_000_000)
    result = service.cash_flow_rebalance_prompts(months=12, as_of_month="2026-05")
    assert result["prompts"] == []
    # Sanity: cascade leftover is exposed for the UI's preview.
    assert result["cascade_leftover_milliunits"] >= 0


def test_rec_paired_with_savings_cushion_when_apply_would_deficit(tmp_path: Path):
    """A calibration rec whose increase would push the cascade negative
    must be paired with a savings cushion drawn from the largest savings
    row that fits the delta."""
    service, database = _setup(tmp_path)
    # Inflow exactly matches outflow so any rec deficit is unambiguous.
    _add_inflow(database, name="Salary", planned_milliunits=2_115_000)
    # Boost a savings row so it's a viable cushion (fixture has Emergency
    # at $200 and Investments at $75).
    savings_id = _set_planned(
        database, category_name="Emergency", milliunits=500_000
    )
    # Trigger an Expenses/Groceries rec ~$100 over plan.
    _seed_overrun(
        database, group="Expenses", category="Groceries", monthly_milliunits=400_000
    )
    result = service.cash_flow_rebalance_prompts(months=12, as_of_month="2026-05")
    paired = [p for p in result["prompts"] if p["kind"] == "rec_paired"]
    assert len(paired) >= 1
    prompt = paired[0]
    assert prompt["increase"]["category_name"] == "Groceries"
    assert prompt["increase"]["delta_milli"] == 100_000
    assert prompt["cushion_status"] == "found"
    assert prompt["decrease"]["category_id"] == savings_id
    assert prompt["decrease"]["delta_milli"] == -100_000
    # Suggested cushion amount = current - delta (drained).
    assert prompt["decrease"]["suggested_milli"] == 400_000


def test_cascade_deficit_prompt_when_plan_currently_negative(tmp_path: Path):
    """Operator hand-edited the plan over income; surface a standalone
    deficit prompt even without a forecast-driven rec."""
    service, database = _setup(tmp_path)
    _add_inflow(database, name="Salary", planned_milliunits=1_000_000)
    # Force outflows above inflow with a $500 cushion in Emergency so it
    # can absorb the deficit.
    _set_planned(database, category_name="Rent", milliunits=2_000_000)
    cushion_id = _set_planned(
        database, category_name="Emergency", milliunits=600_000
    )
    result = service.cash_flow_rebalance_prompts(months=12, as_of_month="2026-05")
    deficit_prompts = [p for p in result["prompts"] if p["kind"] == "cascade_deficit"]
    assert len(deficit_prompts) == 1
    prompt = deficit_prompts[0]
    assert prompt["increase"] is None
    assert prompt["delta_milli"] > 0
    assert prompt["cushion_status"] == "found"
    assert prompt["decrease"]["category_id"] == cushion_id


def test_no_cushion_path_when_savings_zero_and_no_slack(tmp_path: Path):
    """When there's no savings to drain and no discretionary slack, the
    prompt fires but is marked cushion_status=none_available so the UI
    can render the 'adjust manually' fallback."""
    service, database = _setup(tmp_path)
    _add_inflow(database, name="Salary", planned_milliunits=1_500_000)
    # Drain savings so the cushion picker can't use them.
    _set_planned(database, category_name="Emergency", milliunits=0)
    _set_planned(database, category_name="Investments", milliunits=0)
    # Push the plan deeply negative.
    _set_planned(database, category_name="Rent", milliunits=3_000_000)
    result = service.cash_flow_rebalance_prompts(months=12, as_of_month="2026-05")
    deficit_prompts = [p for p in result["prompts"] if p["kind"] == "cascade_deficit"]
    assert deficit_prompts, "expected a deficit prompt"
    assert deficit_prompts[0]["cushion_status"] == "none_available"
    assert deficit_prompts[0]["decrease"] is None


def test_tithe_linked_row_excluded_from_cushion(tmp_path: Path):
    """A tithe-linked row's planned amount is formula-driven; it must not
    be picked as a cushion (the rebalance would silently overwrite the
    tithe formula's value, only to be reverted on the next inflow change)."""
    service, database = _setup(tmp_path)
    _add_inflow(database, name="Salary", planned_milliunits=3_000_000)
    # Boost two savings rows; mark Emergency as tithe-linked so it
    # should be excluded. Investments stays cushion-eligible.
    _set_planned(database, category_name="Emergency", milliunits=400_000)
    investments_id = _set_planned(
        database, category_name="Investments", milliunits=500_000
    )
    with database.connect() as conn:
        conn.execute(
            "UPDATE plan_categories SET tithe_percent = 10 "
            "WHERE category_name = 'Emergency' "
            "AND plan_id = (SELECT id FROM plans WHERE status='active')"
        )
    # Force a deficit and verify the cushion is Investments, not Emergency.
    _set_planned(database, category_name="Rent", milliunits=3_300_000)
    result = service.cash_flow_rebalance_prompts(months=12, as_of_month="2026-05")
    deficit = next(p for p in result["prompts"] if p["kind"] == "cascade_deficit")
    assert deficit["cushion_status"] == "found"
    assert deficit["decrease"]["category_id"] == investments_id


def test_compute_cascade_leftover_matches_inflow_minus_outflow(tmp_path: Path):
    """Direct unit test on the helper: the milliunit math matches the
    frontend's $derived computation so prompts and the chip never disagree."""
    service, database = _setup(tmp_path)
    _add_inflow(database, name="Salary", planned_milliunits=2_500_000)
    with database.connect() as conn:
        leftover = service._compute_cascade_leftover(conn)
        outflow_row = conn.execute(
            """
            SELECT COALESCE(SUM(planned_milliunits), 0) AS total
            FROM plan_categories pc
            JOIN plans p ON p.id = pc.plan_id
            WHERE p.status = 'active' AND pc.kind = 'outflow'
            """
        ).fetchone()
    assert leftover == 2_500_000 - int(outflow_row["total"])
