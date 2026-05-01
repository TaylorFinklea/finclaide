"""Tests for the analytics API endpoints."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from finclaide.analytics import AnalyticsService, _classify_pace
from finclaide.budget_sheet import BudgetImporter
from finclaide.config import AppConfig
from finclaide.database import Database
from finclaide.locking import OperationLock
from tests.workbook_builder import build_budget_workbook


def _seed_data(client, auth_header):
    """Import budget and sync YNAB to populate the database."""
    client.post("/api/budget/import", headers=auth_header)
    client.post("/api/ynab/sync", headers=auth_header)
    client.post("/api/reconcile", headers=auth_header)


def _seed_pace_fixture(tmp_path: Path) -> tuple[AnalyticsService, Database]:
    """Set up a clean DB with one active plan + a few categories. Tests
    can then inject transactions directly to drive `month_pace`."""
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
    service = AnalyticsService(
        config=config,
        database=database,
        operation_lock=OperationLock(),
    )
    return service, database


def _insert_txn(database: Database, *, date_iso: str, group: str, category: str, amount_milliunits: int) -> None:
    """Insert a single transaction with negative amount = expense.

    Schema: id/plan_id/account_id/date/payee_name/memo/cleared/approved/category_id/category_name/group_name/amount_milliunits/deleted/raw_json/updated_at."""
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO transactions(
                id, plan_id, account_id, date, payee_name, memo, cleared, approved,
                category_id, category_name, group_name, amount_milliunits, deleted,
                raw_json, updated_at
            )
            VALUES (?, 'plan-test', 'acct-1', ?, 'Test', NULL, 'cleared', 1,
                    NULL, ?, ?, ?, 0, '{}', ?)
            """,
            (
                f"t{date_iso}-{group}-{category}-{amount_milliunits}",
                date_iso,
                category,
                group,
                -abs(amount_milliunits),
                "2026-04-30T00:00:00+00:00",
            ),
        )


class TestClassifyPace:
    def test_unplanned_returns_negative_sentinel(self):
        factor, status = _classify_pace(planned=0, actual=50_000, days_elapsed=10, days_total=30)
        assert factor == -1.0
        assert status == "unplanned"

    def test_no_spend_yet(self):
        factor, status = _classify_pace(planned=100_000, actual=0, days_elapsed=10, days_total=30)
        assert factor == 0.0
        assert status == "no_spend_yet"

    def test_under_pace(self):
        # 10 / 100 / (10/30) = 0.3 → under
        factor, status = _classify_pace(planned=100_000, actual=10_000, days_elapsed=10, days_total=30)
        assert status == "under_pace"
        assert factor < 0.85

    def test_on_pace(self):
        factor, status = _classify_pace(planned=100_000, actual=33_000, days_elapsed=10, days_total=30)
        assert status == "on_pace"
        assert 0.85 <= factor <= 1.15

    def test_over_pace(self):
        factor, status = _classify_pace(planned=100_000, actual=50_000, days_elapsed=10, days_total=30)
        assert status == "over_pace"

    def test_at_risk(self):
        factor, status = _classify_pace(planned=100_000, actual=60_000, days_elapsed=10, days_total=30)
        assert status == "at_risk"

    def test_blowout(self):
        factor, status = _classify_pace(planned=100_000, actual=80_000, days_elapsed=10, days_total=30)
        assert status == "blowout"
        assert factor > 2.0


class TestMonthPace:
    def test_warming_up_when_days_elapsed_under_3(self, tmp_path: Path):
        service, _ = _seed_pace_fixture(tmp_path)
        result = service.month_pace(month="2026-04", now=date(2026, 4, 2))
        assert result["warming_up"] is True
        assert result["categories"] == []
        assert result["days_elapsed"] == 2

    def test_computes_pace_factor_and_status(self, tmp_path: Path):
        service, database = _seed_pace_fixture(tmp_path)
        # The fixture imports Bills/Rent at $1000 monthly. Spend $700 by day 15.
        _insert_txn(
            database,
            date_iso="2026-04-10",
            group="Bills",
            category="Rent",
            amount_milliunits=700_000,
        )
        result = service.month_pace(month="2026-04", now=date(2026, 4, 15))
        assert result["warming_up"] is False
        assert result["days_elapsed"] == 15
        assert result["days_total"] == 30
        rent = next(
            c for c in result["categories"] if c["category_name"] == "Rent"
        )
        # pace = (700/1000) / (15/30) = 1.4 → over_pace
        assert rent["pace_status"] == "over_pace"
        assert abs(rent["pace_factor"] - 1.4) < 0.01
        assert rent["actual_milliunits"] == 700_000
        assert rent["planned_milliunits"] == 1_000_000
        # Projected = 700 * 30 / 15 = 1400
        assert rent["projected_month_end_milliunits"] == 1_400_000
        assert rent["projected_overage_milliunits"] == 400_000

    def test_excludes_annual_one_time_savings_blocks(self, tmp_path: Path):
        service, _ = _seed_pace_fixture(tmp_path)
        result = service.month_pace(month="2026-04", now=date(2026, 4, 15))
        blocks = {c["block"] for c in result["categories"]}
        assert blocks <= {"monthly", "stipends"}

    def test_handles_unplanned_category(self, tmp_path: Path):
        service, database = _seed_pace_fixture(tmp_path)
        # Spend on a category that's not in the plan: pretend payee posted
        # to a category not in the imported workbook.
        _insert_txn(
            database,
            date_iso="2026-04-08",
            group="Bills",
            category="Mystery",
            amount_milliunits=50_000,
        )
        result = service.month_pace(month="2026-04", now=date(2026, 4, 15))
        # Because Mystery is not a plan_categories row, it doesn't appear
        # in `categories` (we only walk planned rows). This documents the
        # current behavior — unplanned-category surfacing is a Slice 4
        # concern.
        names = [c["category_name"] for c in result["categories"]]
        assert "Mystery" not in names

    def test_past_month_uses_full_month_as_elapsed(self, tmp_path: Path):
        service, database = _seed_pace_fixture(tmp_path)
        _insert_txn(
            database,
            date_iso="2026-03-15",
            group="Bills",
            category="Rent",
            amount_milliunits=1_200_000,
        )
        # "Now" is mid-April; we ask about March.
        result = service.month_pace(month="2026-03", now=date(2026, 4, 15))
        assert result["days_elapsed"] == 31  # March has 31 days, fully past
        assert result["days_remaining"] == 0
        rent = next(c for c in result["categories"] if c["category_name"] == "Rent")
        # planned 1000, actual 1200, full month elapsed → pace ≈ 1.2 → over_pace
        assert rent["pace_status"] == "over_pace"

    def test_sorts_by_projected_overage_desc(self, tmp_path: Path):
        service, database = _seed_pace_fixture(tmp_path)
        _insert_txn(
            database,
            date_iso="2026-04-10",
            group="Bills",
            category="Rent",
            amount_milliunits=900_000,
        )
        _insert_txn(
            database,
            date_iso="2026-04-10",
            group="Bills",
            category="Utilities",
            amount_milliunits=10_000,
        )
        result = service.month_pace(month="2026-04", now=date(2026, 4, 15))
        overages = [c["projected_overage_milliunits"] for c in result["categories"]]
        assert overages == sorted(overages, reverse=True)


class TestCompareMonths:
    def test_compare_returns_categories(self, client, auth_header):
        _seed_data(client, auth_header)
        resp = client.get("/api/analytics/compare?month_a=2026-02&month_b=2026-03", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["month_a"] == "2026-02"
        assert data["month_b"] == "2026-03"
        assert isinstance(data["categories"], list)
        assert "totals" in data

    def test_compare_requires_both_months(self, client, auth_header):
        resp = client.get("/api/analytics/compare?month_a=2026-02", headers=auth_header)
        assert resp.status_code == 400

    def test_compare_requires_auth(self, client):
        resp = client.get("/api/analytics/compare?month_a=2026-02&month_b=2026-03")
        assert resp.status_code == 401


class TestSpendingTrends:
    def test_trends_returns_categories(self, client, auth_header):
        _seed_data(client, auth_header)
        resp = client.get("/api/analytics/trends?months=3", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["lookback_months"] == 3
        assert isinstance(data["categories"], list)

    def test_trends_filter_by_group(self, client, auth_header):
        _seed_data(client, auth_header)
        resp = client.get("/api/analytics/trends?months=3&group=Bills", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        for cat in data["categories"]:
            assert cat["group_name"] == "Bills"


class TestYearEndProjection:
    def test_projection_returns_structure(self, client, auth_header):
        _seed_data(client, auth_header)
        resp = client.get("/api/analytics/projection?as_of_month=2026-03", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["plan_year"] == 2026
        assert data["months_elapsed"] == 3
        assert data["months_remaining"] == 9
        assert isinstance(data["categories"], list)
        assert "totals" in data

    def test_projection_empty_without_import(self, client, auth_header):
        resp = client.get("/api/analytics/projection", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["categories"] == []


class TestAnomalyNarratives:
    """Slice 2: detect_anomalies attaches a narrative payload per item."""

    def test_transaction_anomaly_carries_narrative_with_typical_range(self, tmp_path: Path):
        service, database = _seed_pace_fixture(tmp_path)
        # 6 normal $100 grocery txns + one $700 spike → +sigma triggers anomaly.
        for day in range(1, 7):
            _insert_txn(
                database,
                date_iso=f"2026-04-{day:02d}",
                group="Expenses",
                category="Groceries",
                amount_milliunits=100_000,
            )
        _insert_txn(
            database,
            date_iso="2026-04-08",
            group="Expenses",
            category="Groceries",
            amount_milliunits=700_000,
        )
        result = service.detect_anomalies(months=1, threshold_sigma=1.5, as_of_month="2026-04")
        spikes = [
            a for a in result["transaction_anomalies"]
            if a["category_name"] == "Groceries"
        ]
        assert spikes, "expected the $700 transaction to register"
        narrative = spikes[0]["narrative"]
        assert "typical_low_milliunits" in narrative
        assert "typical_high_milliunits" in narrative
        assert "category_average_milliunits" in narrative
        assert "category_payee_count" in narrative
        assert "Groceries" in narrative["headline"]
        assert "$700" in narrative["headline"] or "$700.00" in narrative["headline"]
        assert narrative["category_payee_count"] >= 1

    def test_category_anomaly_carries_narrative_with_recent_months(self, tmp_path: Path):
        service, database = _seed_pace_fixture(tmp_path)
        # Three baseline months at $200, then an outlier at $600 in the 4th.
        for month, amount in (
            ("2026-01", 200_000),
            ("2026-02", 210_000),
            ("2026-03", 190_000),
            ("2026-04", 600_000),
        ):
            _insert_txn(
                database,
                date_iso=f"{month}-15",
                group="Bills",
                category="Claude",
                amount_milliunits=amount,
            )
        result = service.detect_anomalies(months=4, threshold_sigma=1.0, as_of_month="2026-04")
        outliers = [
            a for a in result["category_anomalies"]
            if a["category_name"] == "Claude" and a["month"] == "2026-04"
        ]
        assert outliers, "expected April 2026 Claude to be flagged"
        narrative = outliers[0]["narrative"]
        assert "Claude" in narrative["headline"]
        assert "2026-04" in narrative["headline"]
        recent_months = [m["month"] for m in narrative["recent_months"]]
        assert "2026-03" in recent_months
        # Narrative context should list recent month/spend pairs.
        assert "2026-03" in narrative["context"]


class TestDetectAnomalies:
    def test_anomalies_returns_structure(self, client, auth_header):
        _seed_data(client, auth_header)
        resp = client.get("/api/analytics/anomalies?months=3", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "transaction_anomalies" in data
        assert "category_anomalies" in data
        assert data["lookback_months"] == 3


class TestBudgetRecommendations:
    def test_recommendations_returns_structure(self, client, auth_header):
        _seed_data(client, auth_header)
        resp = client.get("/api/analytics/recommendations", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "recommendations" in data
        assert "summary" in data


class TestAggregateSpending:
    def test_aggregate_quarter(self, client, auth_header):
        _seed_data(client, auth_header)
        resp = client.get("/api/analytics/aggregate?period=quarter", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["period_type"] == "quarter"
        assert isinstance(data["periods"], dict)

    def test_aggregate_year(self, client, auth_header):
        _seed_data(client, auth_header)
        resp = client.get("/api/analytics/aggregate?period=year", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["period_type"] == "year"


class TestPaceEndpoint:
    def test_pace_endpoint_returns_payload(self, client, auth_header):
        _seed_data(client, auth_header)
        resp = client.get("/api/analytics/pace?month=2026-04", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["month"] == "2026-04"
        assert "warming_up" in data
        assert isinstance(data["categories"], list)
        assert "totals" in data

    def test_ui_api_pace_endpoint_mirrors_api(self, app_factory):
        app = app_factory()
        client = app.test_client()
        client.post("/api/budget/import", headers={"Authorization": "Bearer test-token"})
        resp = client.get("/ui-api/analytics/pace?month=2026-04")
        assert resp.status_code == 200
        assert resp.get_json()["month"] == "2026-04"


class TestHealthCheck:
    def test_health_returns_structure(self, client, auth_header):
        _seed_data(client, auth_header)
        resp = client.get("/api/analytics/health", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["overall_status"] in {"healthy", "warning", "critical"}
        assert isinstance(data["alerts"], list)
        assert "stats" in data

    def test_health_warns_without_data(self, client, auth_header):
        resp = client.get("/api/analytics/health", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        # Should warn about no budget import and no sync
        assert data["overall_status"] in {"warning", "critical"}
        categories = [a["category"] for a in data["alerts"]]
        assert "no_budget" in categories or "stale_data" in categories
