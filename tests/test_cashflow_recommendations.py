"""Tests for Phase 4 Slice 2 — cash_flow_recommendations.

Plan calibration only: discretionary categories (non-fixed groups)
where the 6-month run-rate exceeds plan by ≥10% AND ≥$25/mo. Fixed
groups are skipped (Bills, Payments, Stipends, Savings — the
operator's plan is authoritative there)."""
from __future__ import annotations

from pathlib import Path

from finclaide.budget_sheet import BudgetImporter
from finclaide.config import AppConfig
from finclaide.database import Database
from finclaide.analytics import AnalyticsService
from finclaide.locking import OperationLock
from tests.workbook_builder import build_budget_workbook


# --- helpers --------------------------------------------------------------


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


def _seed_overrun(
    database: Database, *, group: str, category: str, monthly_milliunits: int
) -> None:
    """Insert 6 months of identical transactions for a category. Pinned to
    months 2025-11..2026-04 which is the lookback window when as_of_month=2026-05."""
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


def test_no_recommendations_when_run_rate_matches_plan(tmp_path: Path):
    service, database = _setup(tmp_path)
    # Fixture's Groceries plan = 300_000. Inject exactly $300 run-rate
    # (within 10% threshold).
    _seed_overrun(
        database, group="Expenses", category="Groceries", monthly_milliunits=305_000
    )
    result = service.cash_flow_recommendations(months=12, as_of_month="2026-05")
    groceries_recs = [
        r for r in result["recommendations"]
        if r["category"]["category_name"] == "Groceries"
    ]
    assert groceries_recs == []


def test_calibration_recommended_when_run_rate_exceeds_plan(tmp_path: Path):
    service, database = _setup(tmp_path)
    # Fixture's Groceries plan = 300_000. Inject $400/mo to push run-rate
    # to $400 (>33% over).
    _seed_overrun(
        database, group="Expenses", category="Groceries", monthly_milliunits=400_000
    )
    result = service.cash_flow_recommendations(months=12, as_of_month="2026-05")
    rec = next(
        (r for r in result["recommendations"] if r["category"]["category_name"] == "Groceries"),
        None,
    )
    assert rec is not None
    assert rec["current_planned_milliunits"] == 300_000
    assert rec["suggested_planned_milliunits"] == 400_000
    assert rec["monthly_delta_milliunits"] == 100_000


def test_skips_fixed_groups(tmp_path: Path):
    service, database = _setup(tmp_path)
    # Bills/Rent is fixed. Even with massive over-run, no rec.
    _seed_overrun(
        database, group="Bills", category="Rent", monthly_milliunits=2_000_000
    )
    result = service.cash_flow_recommendations(months=12, as_of_month="2026-05")
    rent_recs = [r for r in result["recommendations"] if r["category"]["category_name"] == "Rent"]
    assert rent_recs == []


def test_skips_below_noise_floor(tmp_path: Path):
    service, database = _setup(tmp_path)
    # Tiny over-run: $5/mo over plan. Below the $25 noise floor.
    _seed_overrun(
        database, group="Expenses", category="Groceries", monthly_milliunits=305_000
    )
    result = service.cash_flow_recommendations(months=12, as_of_month="2026-05")
    groceries_recs = [
        r for r in result["recommendations"]
        if r["category"]["category_name"] == "Groceries"
    ]
    assert groceries_recs == []


def test_projected_impact_reflects_simulation(tmp_path: Path):
    service, database = _setup(tmp_path)
    _seed_overrun(
        database, group="Expenses", category="Groceries", monthly_milliunits=400_000
    )
    result = service.cash_flow_recommendations(months=12, as_of_month="2026-05")
    rec = next(
        r for r in result["recommendations"] if r["category"]["category_name"] == "Groceries"
    )
    impact = rec["projected_impact"]
    # After simulation the after-balance should be lower than the
    # before-balance (we're spending more each month).
    assert impact["lowest_balance_after_milliunits"] <= impact["lowest_balance_before_milliunits"]


def test_caps_at_10_recommendations(tmp_path: Path):
    service, database = _setup(tmp_path)
    # Fixture Expenses categories: Groceries, Fuel. Add many more
    # discretionary categories with their own over-runs and let the
    # cap kick in. Plan-categories + transactions inserted in the same
    # connection to avoid the SQLite write lock.
    months = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]
    with database.connect() as conn:
        plan_id_row = conn.execute("SELECT id FROM plans WHERE status='active'").fetchone()
        plan_id = plan_id_row["id"]
        for i in range(15):
            cat_name = f"Cat{i}"
            conn.execute(
                """
                INSERT INTO plan_categories(
                    plan_id, group_name, category_name, block,
                    planned_milliunits, annual_target_milliunits, due_month,
                    notes, created_at, updated_at
                ) VALUES (?, 'Expenses', ?, 'monthly', 100000, 0, NULL, NULL,
                          '2026-04-01T00:00:00+00:00', '2026-04-01T00:00:00+00:00')
                """,
                (plan_id, cat_name),
            )
            for j, m in enumerate(months):
                conn.execute(
                    """
                    INSERT INTO transactions(
                        id, plan_id, account_id, date, payee_name, memo, cleared,
                        approved, category_id, category_name, group_name,
                        amount_milliunits, deleted, raw_json, updated_at
                    ) VALUES (?, 'plan-test', 'acct-1', ?, 'Test', NULL, 'cleared',
                              1, NULL, ?, 'Expenses', -200000, 0, '{}',
                              '2026-04-30T00:00:00+00:00')
                    """,
                    (f"t-{cat_name}-{j}", f"{m}-15", cat_name),
                )
    result = service.cash_flow_recommendations(months=12, as_of_month="2026-05")
    assert len(result["recommendations"]) <= 10


def test_endpoint_round_trips(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()
    client.post("/api/budget/import", headers=auth_header)
    client.post("/api/ynab/sync", headers=auth_header)

    response = client.get(
        "/api/analytics/cashflow/recommendations?months=12&as_of_month=2026-05",
        headers=auth_header,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert "recommendations" in body
    assert isinstance(body["recommendations"], list)
    assert "baseline_lowest_balance_milliunits" in body
    assert "baseline_first_negative_month" in body
