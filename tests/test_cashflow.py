"""Tests for Phase 4 Slice 1 — cash_flow_timeline.

Validates the hybrid forecast model: fixed groups (Bills, Payments,
Credit Card Payments, Stipends, Savings) project from plan; everything
else uses 6-month run-rate. Annual + one_time categories with
`due_month` set lump in that month; otherwise smoothed across 12
months. Stipends are inflows; everything else is outflow."""
from __future__ import annotations

from pathlib import Path

from finclaide.analytics import (
    AnalyticsService,
    _add_months,
    _is_fixed_group,
    _month_key,
)
from finclaide.budget_sheet import BudgetImporter
from finclaide.config import AppConfig
from finclaide.database import Database
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


def _insert_account(
    database: Database, *, account_id: str, balance_milliunits: int
) -> None:
    with database.connect() as conn:
        conn.execute(
            """
            INSERT INTO accounts(
                id, plan_id, name, type, on_budget, closed,
                balance_milliunits, raw_json, updated_at
            ) VALUES (?, 'plan-123', 'Test', 'checking', 1, 0, ?,
                      '{}', '2026-05-01T00:00:00+00:00')
            """,
            (account_id, balance_milliunits),
        )


def _insert_txn(
    database: Database,
    *,
    txn_id: str,
    date_iso: str,
    group: str,
    category: str,
    amount_milliunits: int,
) -> None:
    """Negative amounts = expenses (matches the YNAB sign convention
    used elsewhere in the codebase)."""
    with database.connect() as conn:
        conn.execute(
            """
            INSERT INTO transactions(
                id, plan_id, account_id, date, payee_name, memo, cleared,
                approved, category_id, category_name, group_name,
                amount_milliunits, deleted, raw_json, updated_at
            ) VALUES (?, 'plan-123', 'acct-1', ?, 'Test', NULL, 'cleared',
                      1, NULL, ?, ?, ?, 0, '{}', '2026-05-01T00:00:00+00:00')
            """,
            (txn_id, date_iso, category, group, -abs(amount_milliunits)),
        )


# --- pure-helper unit tests -----------------------------------------------


def test_is_fixed_group_classifies_default_groups():
    assert _is_fixed_group("Bills") is True
    assert _is_fixed_group("Payments") is True
    assert _is_fixed_group("Credit Card Payments") is True
    assert _is_fixed_group("Stipends") is True
    assert _is_fixed_group("Savings") is True


def test_is_fixed_group_treats_others_as_discretionary():
    assert _is_fixed_group("Expenses") is False
    assert _is_fixed_group("Fun") is False
    assert _is_fixed_group("Yearly") is False
    assert _is_fixed_group("One Time Purchase") is False


def test_add_months_wraps_year():
    assert _add_months(2026, 12, 1) == (2027, 1)
    assert _add_months(2026, 5, 12) == (2027, 5)
    assert _add_months(2026, 5, 0) == (2026, 5)


# --- cash_flow_timeline tests --------------------------------------------


def test_returns_n_months_starting_at_as_of_month(tmp_path: Path):
    service, _ = _setup(tmp_path)
    result = service.cash_flow_timeline(months=12, as_of_month="2026-05")
    assert result["as_of_month"] == "2026-05"
    assert len(result["months"]) == 12
    assert result["months"][0]["month"] == "2026-05"
    assert result["months"][11]["month"] == "2027-04"


def test_starting_balance_sums_open_positive_accounts(tmp_path: Path):
    service, database = _setup(tmp_path)
    _insert_account(database, account_id="acct-1", balance_milliunits=5_000_000)
    _insert_account(database, account_id="acct-2", balance_milliunits=2_500_000)
    # Negative balance (liability) is excluded.
    _insert_account(database, account_id="acct-cc", balance_milliunits=-300_000)
    result = service.cash_flow_timeline(months=12, as_of_month="2026-05")
    assert result["starting_balance_milliunits"] == 7_500_000


def test_fixed_group_projects_from_plan_each_month(tmp_path: Path):
    service, _ = _setup(tmp_path)
    result = service.cash_flow_timeline(
        months=3,
        as_of_month="2026-05",
        starting_balance_override_milliunits=10_000_000,
    )
    # Fixture: Bills/Rent has planned 1_000_000. Should appear as an
    # outflow contributor in every month with basis="plan".
    for month_payload in result["months"]:
        rent = next(
            (
                c
                for c in month_payload["top_outflow_categories"]
                if c["category_name"] == "Rent"
            ),
            None,
        )
        # Top-outflow is capped at 3, but Rent is the biggest monthly
        # in the fixture, so it should be present.
        assert rent is not None, month_payload["month"]
        assert rent["milliunits"] == 1_000_000
        assert rent["basis"] == "plan"


def test_discretionary_group_uses_run_rate(tmp_path: Path):
    service, database = _setup(tmp_path)
    # Fixture Groceries plan = 300_000. Inject 6 months of $400 spend
    # so the run-rate is 400_000 (vs. the 300_000 plan).
    for i in range(6):
        month_iso = f"2025-{11 + 0 + (i if i < 2 else 0):02d}-15" if i < 2 else f"2026-{i - 1:02d}-15"
        # Simpler: use months 2025-11 through 2026-04
        pass
    months = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]
    for i, m in enumerate(months):
        _insert_txn(
            database,
            txn_id=f"t-groc-{i}",
            date_iso=f"{m}-15",
            group="Expenses",
            category="Groceries",
            amount_milliunits=400_000,
        )
    result = service.cash_flow_timeline(
        months=2,
        as_of_month="2026-05",
        starting_balance_override_milliunits=10_000_000,
    )
    # First month's top outflows should include Groceries at run-rate
    # 400_000, basis="run_rate".
    first_month = result["months"][0]
    groceries = next(
        c for c in first_month["top_outflow_categories"] if c["category_name"] == "Groceries"
    )
    assert groceries["milliunits"] == 400_000
    assert groceries["basis"] == "run_rate"


def test_discretionary_falls_back_to_plan_when_no_history(tmp_path: Path):
    service, _ = _setup(tmp_path)
    # No injected transactions → no run-rate. Fixture Groceries plan
    # = 300_000.
    result = service.cash_flow_timeline(
        months=2,
        as_of_month="2026-05",
        starting_balance_override_milliunits=10_000_000,
    )
    first_month = result["months"][0]
    groceries = next(
        (c for c in first_month["top_outflow_categories"] if c["category_name"] == "Groceries"),
        None,
    )
    assert groceries is not None
    assert groceries["milliunits"] == 300_000
    assert groceries["basis"] == "plan"


def test_stipends_are_inflows(tmp_path: Path):
    service, database = _setup(tmp_path)
    # The legacy fixture's Stipends are inflows totaling $150 (S Stipend
    # 100 + T Stipend 50).
    result = service.cash_flow_timeline(
        months=1,
        as_of_month="2026-05",
        starting_balance_override_milliunits=10_000_000,
    )
    assert result["months"][0]["inflows_milliunits"] == 150_000


def test_annual_with_due_month_lumps_in_that_month(tmp_path: Path):
    service, database = _setup(tmp_path)
    # The legacy fixture's "Vacation" is a Yearly category with
    # due_month=6 (June) and annual_target=1_200_000. In a window
    # starting May 2026, it should appear in month index 1 (June).
    result = service.cash_flow_timeline(
        months=12,
        as_of_month="2026-05",
        starting_balance_override_milliunits=10_000_000,
    )
    may = result["months"][0]
    june = result["months"][1]
    may_lumps = {l["category_name"] for l in may["obligation_lumps"]}
    june_lumps = {l["category_name"] for l in june["obligation_lumps"]}
    assert "Vacation" not in may_lumps
    assert "Vacation" in june_lumps
    vacation = next(l for l in june["obligation_lumps"] if l["category_name"] == "Vacation")
    assert vacation["milliunits"] == 1_200_000


def test_first_negative_month_set_when_balance_goes_negative(tmp_path: Path):
    service, _ = _setup(tmp_path)
    # Tiny starting balance and the fixture's outflows will quickly
    # push it negative (Rent alone is $1000/mo).
    result = service.cash_flow_timeline(
        months=12,
        as_of_month="2026-05",
        starting_balance_override_milliunits=500_000,
    )
    assert result["first_negative_month"] is not None
    assert result["shortfall_drivers"] is not None
    assert len(result["shortfall_drivers"]) <= 3


def test_first_negative_month_null_when_always_positive(tmp_path: Path):
    service, _ = _setup(tmp_path)
    # Massive starting balance — never goes negative.
    result = service.cash_flow_timeline(
        months=12,
        as_of_month="2026-05",
        starting_balance_override_milliunits=1_000_000_000,
    )
    assert result["first_negative_month"] is None
    assert result["shortfall_drivers"] is None


def test_shortfall_drivers_are_top_3_outflow_categories(tmp_path: Path):
    service, _ = _setup(tmp_path)
    result = service.cash_flow_timeline(
        months=12,
        as_of_month="2026-05",
        starting_balance_override_milliunits=0,
    )
    assert result["first_negative_month"] is not None
    drivers = result["shortfall_drivers"]
    assert drivers is not None
    # Sorted descending by total_milliunits.
    totals = [d["total_milliunits"] for d in drivers]
    assert totals == sorted(totals, reverse=True)


def test_cashflow_endpoint_round_trips(app_factory, auth_header, tmp_path: Path):
    workbook = build_budget_workbook(tmp_path / "Budget.xlsx")
    app = app_factory(workbook_path=workbook)
    client = app.test_client()
    client.post("/api/budget/import", headers=auth_header)
    client.post("/api/ynab/sync", headers=auth_header)

    response = client.get(
        "/api/analytics/cashflow?months=6&as_of_month=2026-05",
        headers=auth_header,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["as_of_month"] == "2026-05"
    assert body["months_ahead"] == 6
    assert len(body["months"]) == 6
    assert "lowest_balance" in body
    assert "first_negative_month" in body


# Silence unused-import warning when `_month_key` is not directly
# asserted but the helper file references it via _add_months tests
# above. Touch it once so the module-level helper stays exercised.
def test_month_key_format():
    assert _month_key(2026, 5) == "2026-05"
    assert _month_key(2027, 12) == "2027-12"
