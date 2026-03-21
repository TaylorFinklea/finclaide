"""Tests for the analytics API endpoints."""
from __future__ import annotations


def _seed_data(client, auth_header):
    """Import budget and sync YNAB to populate the database."""
    client.post("/api/budget/import", headers=auth_header)
    client.post("/api/ynab/sync", headers=auth_header)
    client.post("/api/reconcile", headers=auth_header)


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
