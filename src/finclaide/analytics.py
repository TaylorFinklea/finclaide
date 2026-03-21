from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from finclaide.config import AppConfig
from finclaide.database import Database, utc_now
from finclaide.locking import OperationLock


def _n_months_ago(n: int, reference: date | None = None) -> str:
    ref = reference or datetime.now(UTC).date()
    year, month = ref.year, ref.month
    for _ in range(n):
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return f"{year:04d}-{month:02d}"


def _current_month_label() -> str:
    now = datetime.now(UTC).date()
    return now.strftime("%Y-%m")


def _months_in_year(plan_year: int, through_month: int) -> list[str]:
    return [f"{plan_year:04d}-{m:02d}" for m in range(1, through_month + 1)]


def _stddev(values: list[int | float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


@dataclass
class AnalyticsService:
    config: AppConfig
    database: Database
    operation_lock: OperationLock

    # ------------------------------------------------------------------
    # compare_months
    # ------------------------------------------------------------------

    def compare_months(self, month_a: str, month_b: str) -> dict[str, Any]:
        """Compare spending between two months at the category level."""
        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(c.group_name, t.group_name) AS group_name,
                    COALESCE(c.name, t.category_name) AS category_name,
                    substr(t.date, 1, 7) AS month,
                    SUM(CASE WHEN t.amount_milliunits < 0 THEN -1 * t.amount_milliunits ELSE 0 END) AS spend_milliunits
                FROM transactions t
                LEFT JOIN categories c ON c.id = t.category_id
                WHERE t.deleted = 0
                  AND substr(t.date, 1, 7) IN (?, ?)
                GROUP BY 1, 2, 3
                """,
                (month_a, month_b),
            ).fetchall()

        by_cat: dict[tuple[str, str], dict[str, int]] = {}
        for row in rows:
            key = (row["group_name"] or "", row["category_name"] or "")
            entry = by_cat.setdefault(key, {"a": 0, "b": 0})
            if row["month"] == month_a:
                entry["a"] = int(row["spend_milliunits"])
            else:
                entry["b"] = int(row["spend_milliunits"])

        categories = []
        total_a = total_b = 0
        for (group_name, category_name), amounts in sorted(by_cat.items()):
            delta = amounts["b"] - amounts["a"]
            pct = round(delta / amounts["a"] * 100, 1) if amounts["a"] else None
            categories.append({
                "group_name": group_name,
                "category_name": category_name,
                "month_a_milliunits": amounts["a"],
                "month_b_milliunits": amounts["b"],
                "delta_milliunits": delta,
                "delta_percent": pct,
            })
            total_a += amounts["a"]
            total_b += amounts["b"]

        return {
            "month_a": month_a,
            "month_b": month_b,
            "categories": categories,
            "totals": {
                "month_a_milliunits": total_a,
                "month_b_milliunits": total_b,
                "delta_milliunits": total_b - total_a,
            },
        }

    # ------------------------------------------------------------------
    # spending_trends
    # ------------------------------------------------------------------

    def spending_trends(
        self,
        months: int = 6,
        group_name: str | None = None,
        category_name: str | None = None,
    ) -> dict[str, Any]:
        """Monthly spending time series with trend analysis."""
        since = _n_months_ago(months)
        conditions = ["t.deleted = 0", "t.date >= ?"]
        params: list[Any] = [f"{since}-01"]
        if group_name:
            conditions.append("COALESCE(c.group_name, t.group_name) = ?")
            params.append(group_name)
        if category_name:
            conditions.append("COALESCE(c.name, t.category_name) = ?")
            params.append(category_name)
        where = " AND ".join(conditions)

        with self.database.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    substr(t.date, 1, 7) AS month,
                    COALESCE(c.group_name, t.group_name) AS group_name,
                    COALESCE(c.name, t.category_name) AS category_name,
                    SUM(CASE WHEN t.amount_milliunits < 0 THEN -1 * t.amount_milliunits ELSE 0 END) AS spend_milliunits,
                    COUNT(*) AS transaction_count
                FROM transactions t
                LEFT JOIN categories c ON c.id = t.category_id
                WHERE {where}
                GROUP BY 1, 2, 3
                ORDER BY 1, 2, 3
                """,
                tuple(params),
            ).fetchall()

        # Group by category, build monthly series
        cat_data: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in rows:
            key = (row["group_name"] or "", row["category_name"] or "")
            cat_data.setdefault(key, []).append({
                "month": row["month"],
                "spend_milliunits": int(row["spend_milliunits"]),
                "transaction_count": int(row["transaction_count"]),
            })

        categories = []
        for (grp, cat), series in sorted(cat_data.items()):
            values = [s["spend_milliunits"] for s in series]
            avg = int(sum(values) / len(values)) if values else 0
            std = _stddev(values)
            cv = round(std / avg, 2) if avg else 0.0

            # Simple trend: compare first half vs second half
            if len(values) >= 2:
                mid = len(values) // 2
                first_half_avg = sum(values[:mid]) / mid
                second_half_avg = sum(values[mid:]) / (len(values) - mid)
                if second_half_avg > first_half_avg * 1.1:
                    trend = "rising"
                elif second_half_avg < first_half_avg * 0.9:
                    trend = "falling"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            categories.append({
                "group_name": grp,
                "category_name": cat,
                "months": series,
                "average_milliunits": avg,
                "min_milliunits": min(values) if values else 0,
                "max_milliunits": max(values) if values else 0,
                "trend_direction": trend,
                "coefficient_of_variation": cv,
            })

        return {
            "lookback_months": months,
            "since": since,
            "categories": categories,
        }

    # ------------------------------------------------------------------
    # year_end_projection
    # ------------------------------------------------------------------

    def year_end_projection(self, as_of_month: str | None = None) -> dict[str, Any]:
        """Project year-end using run rate for completed months, plan for future."""
        current = as_of_month or _current_month_label()
        month_number = int(current.split("-")[1])

        with self.database.connect() as conn:
            latest_import = conn.execute("SELECT * FROM v_latest_budget_import").fetchone()
            if latest_import is None:
                return {
                    "as_of_month": current,
                    "plan_year": None,
                    "months_elapsed": month_number,
                    "months_remaining": 12 - month_number,
                    "categories": [],
                    "totals": {},
                }

            plan_year = int(latest_import["plan_year"])
            # Get planned categories
            planned = conn.execute(
                """
                SELECT group_name, category_name, block,
                       planned_milliunits, annual_target_milliunits
                FROM v_latest_planned_categories
                ORDER BY group_name, category_name
                """
            ).fetchall()

            # Get actual monthly spend per category for completed months
            actual_rows = conn.execute(
                """
                SELECT
                    COALESCE(c.group_name, t.group_name) AS group_name,
                    COALESCE(c.name, t.category_name) AS category_name,
                    substr(t.date, 1, 7) AS month,
                    SUM(CASE WHEN t.amount_milliunits < 0 THEN -1 * t.amount_milliunits ELSE 0 END) AS spend_milliunits
                FROM transactions t
                LEFT JOIN categories c ON c.id = t.category_id
                WHERE t.deleted = 0
                  AND substr(t.date, 1, 4) = ?
                GROUP BY 1, 2, 3
                """,
                (str(plan_year),),
            ).fetchall()

        # Build lookup: (group, category) -> {month: spend}
        actual_by_cat: dict[tuple[str, str], dict[str, int]] = {}
        for row in actual_rows:
            key = (row["group_name"] or "", row["category_name"] or "")
            actual_by_cat.setdefault(key, {})[row["month"]] = int(row["spend_milliunits"])

        categories = []
        total_planned = total_projected = 0
        for row in planned:
            key = (row["group_name"], row["category_name"])
            monthly_actuals = actual_by_cat.get(key, {})
            actual_ytd = sum(monthly_actuals.values())
            active_months = len(monthly_actuals)

            planned_monthly = int(row["planned_milliunits"])
            annual_target = int(row["annual_target_milliunits"]) or (planned_monthly * 12)

            if active_months > 0:
                run_rate = actual_ytd // active_months
            else:
                run_rate = planned_monthly

            remaining = 12 - month_number
            projected_annual = actual_ytd + (run_rate * remaining)

            categories.append({
                "group_name": row["group_name"],
                "category_name": row["category_name"],
                "planned_annual_milliunits": annual_target,
                "actual_ytd_milliunits": actual_ytd,
                "projected_annual_milliunits": projected_annual,
                "projected_variance_milliunits": projected_annual - annual_target,
                "run_rate_monthly_milliunits": run_rate,
                "planned_monthly_milliunits": planned_monthly,
            })
            total_planned += annual_target
            total_projected += projected_annual

        return {
            "as_of_month": current,
            "plan_year": plan_year,
            "months_elapsed": month_number,
            "months_remaining": 12 - month_number,
            "categories": categories,
            "totals": {
                "planned_annual_milliunits": total_planned,
                "projected_annual_milliunits": total_projected,
                "projected_variance_milliunits": total_projected - total_planned,
            },
        }

    # ------------------------------------------------------------------
    # detect_anomalies
    # ------------------------------------------------------------------

    def detect_anomalies(
        self,
        months: int = 3,
        threshold_sigma: float = 2.0,
    ) -> dict[str, Any]:
        """Find unusual transactions and category-level spending spikes."""
        since = f"{_n_months_ago(months)}-01"

        with self.database.connect() as conn:
            # Per-category stats
            cat_stats_rows = conn.execute(
                """
                SELECT
                    COALESCE(c.group_name, t.group_name) AS group_name,
                    COALESCE(c.name, t.category_name) AS category_name,
                    t.id,
                    t.date,
                    t.payee_name,
                    t.memo,
                    ABS(t.amount_milliunits) AS abs_amount
                FROM transactions t
                LEFT JOIN categories c ON c.id = t.category_id
                WHERE t.deleted = 0
                  AND t.date >= ?
                  AND t.amount_milliunits < 0
                ORDER BY group_name, category_name, t.date
                """,
                (since,),
            ).fetchall()

            # Monthly totals per category for category-level anomalies
            monthly_rows = conn.execute(
                """
                SELECT
                    COALESCE(c.group_name, t.group_name) AS group_name,
                    COALESCE(c.name, t.category_name) AS category_name,
                    substr(t.date, 1, 7) AS month,
                    SUM(CASE WHEN t.amount_milliunits < 0 THEN -1 * t.amount_milliunits ELSE 0 END) AS spend_milliunits
                FROM transactions t
                LEFT JOIN categories c ON c.id = t.category_id
                WHERE t.deleted = 0
                  AND t.date >= ?
                GROUP BY 1, 2, 3
                """,
                (since,),
            ).fetchall()

        # Transaction anomalies: group transactions by category, compute per-category stats
        by_cat: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in cat_stats_rows:
            key = (row["group_name"] or "", row["category_name"] or "")
            by_cat.setdefault(key, []).append({
                "id": row["id"],
                "date": row["date"],
                "payee_name": row["payee_name"],
                "memo": row["memo"],
                "abs_amount": int(row["abs_amount"]),
            })

        transaction_anomalies = []
        for (grp, cat), txns in by_cat.items():
            if len(txns) < 3:
                continue
            amounts = [t["abs_amount"] for t in txns]
            mean = sum(amounts) / len(amounts)
            std = _stddev(amounts)
            if std == 0:
                continue
            for txn in txns:
                sigma = (txn["abs_amount"] - mean) / std
                if sigma >= threshold_sigma:
                    transaction_anomalies.append({
                        "id": txn["id"],
                        "date": txn["date"],
                        "payee_name": txn["payee_name"],
                        "amount_milliunits": -txn["abs_amount"],
                        "group_name": grp,
                        "category_name": cat,
                        "category_mean_milliunits": int(mean),
                        "category_stddev_milliunits": int(std),
                        "sigma_distance": round(sigma, 1),
                    })

        # Category-level anomalies: monthly totals
        cat_monthly: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in monthly_rows:
            key = (row["group_name"] or "", row["category_name"] or "")
            cat_monthly.setdefault(key, []).append({
                "month": row["month"],
                "spend_milliunits": int(row["spend_milliunits"]),
            })

        category_anomalies = []
        for (grp, cat), monthly in cat_monthly.items():
            if len(monthly) < 2:
                continue
            values = [m["spend_milliunits"] for m in monthly]
            mean = sum(values) / len(values)
            std = _stddev(values)
            if std == 0:
                continue
            for entry in monthly:
                sigma = (entry["spend_milliunits"] - mean) / std
                if sigma >= threshold_sigma:
                    category_anomalies.append({
                        "group_name": grp,
                        "category_name": cat,
                        "month": entry["month"],
                        "spend_milliunits": entry["spend_milliunits"],
                        "historical_mean_milliunits": int(mean),
                        "historical_stddev_milliunits": int(std),
                        "sigma_distance": round(sigma, 1),
                    })

        return {
            "lookback_months": months,
            "threshold_sigma": threshold_sigma,
            "transaction_anomalies": sorted(transaction_anomalies, key=lambda a: -a["sigma_distance"]),
            "category_anomalies": sorted(category_anomalies, key=lambda a: -a["sigma_distance"]),
        }

    # ------------------------------------------------------------------
    # budget_recommendations
    # ------------------------------------------------------------------

    def budget_recommendations(self) -> dict[str, Any]:
        """Concrete budget adjustment suggestions based on actual spending."""
        current = _current_month_label()
        projection = self.year_end_projection(current)
        trends = self.spending_trends(months=6)

        # Build trend lookup
        trend_lookup: dict[tuple[str, str], dict[str, Any]] = {}
        for cat in trends["categories"]:
            trend_lookup[(cat["group_name"], cat["category_name"])] = cat

        recommendations = []
        for cat in projection.get("categories", []):
            variance = cat["projected_variance_milliunits"]
            planned = cat["planned_monthly_milliunits"]
            run_rate = cat["run_rate_monthly_milliunits"]
            key = (cat["group_name"], cat["category_name"])
            trend_info = trend_lookup.get(key, {})

            # Only flag meaningful variances (> $5/month)
            if abs(variance) < 5000 * 12:
                continue

            if variance > 0 and run_rate > planned:
                action = "increase_budget"
                reason = (
                    f"Averaging ${run_rate // 1000}/mo against ${planned // 1000} plan. "
                    f"Projected ${variance // 1000} annual overage."
                )
                suggested = run_rate
            elif variance < 0 and run_rate < planned:
                action = "reduce_budget"
                reason = (
                    f"Averaging ${run_rate // 1000}/mo against ${planned // 1000} plan. "
                    f"Projected ${abs(variance) // 1000} annual surplus."
                )
                suggested = run_rate
            else:
                continue

            cv = trend_info.get("coefficient_of_variation", 0)
            confidence = "high" if cv < 0.3 else "medium" if cv < 0.6 else "low"

            recommendations.append({
                "group_name": cat["group_name"],
                "category_name": cat["category_name"],
                "action": action,
                "reason": reason,
                "current_planned_milliunits": planned,
                "suggested_planned_milliunits": suggested,
                "projected_annual_impact_milliunits": variance,
                "confidence": confidence,
                "trend_direction": trend_info.get("trend_direction", "stable"),
            })

        recommendations.sort(key=lambda r: -abs(r["projected_annual_impact_milliunits"]))

        over_count = sum(1 for r in recommendations if r["action"] == "increase_budget")
        under_count = sum(1 for r in recommendations if r["action"] == "reduce_budget")

        return {
            "as_of_month": current,
            "recommendations": recommendations,
            "summary": {
                "total_projected_variance_milliunits": projection.get("totals", {}).get("projected_variance_milliunits", 0),
                "categories_over_budget": over_count,
                "categories_under_budget": under_count,
            },
        }

    # ------------------------------------------------------------------
    # aggregate_spending
    # ------------------------------------------------------------------

    def aggregate_spending(
        self,
        period: str = "quarter",
        group_name: str | None = None,
        category_name: str | None = None,
    ) -> dict[str, Any]:
        """Aggregate spending by quarter or year."""
        if period == "quarter":
            period_expr = """
                substr(t.date, 1, 4) || '-Q' ||
                CASE
                    WHEN CAST(substr(t.date, 6, 2) AS INTEGER) <= 3 THEN '1'
                    WHEN CAST(substr(t.date, 6, 2) AS INTEGER) <= 6 THEN '2'
                    WHEN CAST(substr(t.date, 6, 2) AS INTEGER) <= 9 THEN '3'
                    ELSE '4'
                END
            """
        else:
            period_expr = "substr(t.date, 1, 4)"

        conditions = ["t.deleted = 0"]
        params: list[Any] = []
        if group_name:
            conditions.append("COALESCE(c.group_name, t.group_name) = ?")
            params.append(group_name)
        if category_name:
            conditions.append("COALESCE(c.name, t.category_name) = ?")
            params.append(category_name)
        where = " AND ".join(conditions)

        with self.database.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    ({period_expr}) AS period,
                    COALESCE(c.group_name, t.group_name) AS group_name,
                    COALESCE(c.name, t.category_name) AS category_name,
                    SUM(CASE WHEN t.amount_milliunits < 0 THEN -1 * t.amount_milliunits ELSE 0 END) AS spend_milliunits,
                    COUNT(*) AS transaction_count
                FROM transactions t
                LEFT JOIN categories c ON c.id = t.category_id
                WHERE {where}
                GROUP BY 1, 2, 3
                ORDER BY 1, 2, 3
                """,
                tuple(params),
            ).fetchall()

        periods: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            periods.setdefault(row["period"], []).append({
                "group_name": row["group_name"] or "",
                "category_name": row["category_name"] or "",
                "spend_milliunits": int(row["spend_milliunits"]),
                "transaction_count": int(row["transaction_count"]),
            })

        return {
            "period_type": period,
            "periods": {
                p: {
                    "categories": cats,
                    "total_spend_milliunits": sum(c["spend_milliunits"] for c in cats),
                }
                for p, cats in sorted(periods.items())
            },
        }

    # ------------------------------------------------------------------
    # financial_health_check
    # ------------------------------------------------------------------

    def financial_health_check(self) -> dict[str, Any]:
        """Comprehensive health check with prioritized alerts."""
        alerts: list[dict[str, Any]] = []

        with self.database.connect() as conn:
            # Check sync freshness
            sync_state = None
            if self.config.ynab_plan_id:
                sync_state = conn.execute(
                    "SELECT * FROM ynab_sync_state WHERE plan_id = ?",
                    (self.config.ynab_plan_id,),
                ).fetchone()

            if sync_state and sync_state["last_synced_at"]:
                synced_at = datetime.fromisoformat(sync_state["last_synced_at"])
                hours_stale = (datetime.now(UTC) - synced_at).total_seconds() / 3600
                if hours_stale > 72:
                    alerts.append({
                        "severity": "critical",
                        "category": "stale_data",
                        "title": f"YNAB sync is {int(hours_stale)} hours old",
                        "detail": "Run refresh_all to update. Data may be significantly out of date.",
                    })
                elif hours_stale > 24:
                    alerts.append({
                        "severity": "warning",
                        "category": "stale_data",
                        "title": f"YNAB sync is {int(hours_stale)} hours old",
                        "detail": "Run sync_ynab to update.",
                    })
            elif self.config.ynab_plan_id:
                alerts.append({
                    "severity": "warning",
                    "category": "stale_data",
                    "title": "YNAB has never been synced",
                    "detail": "Run sync_ynab to pull initial data.",
                })

            # Check reconciliation
            latest_recon = conn.execute("SELECT * FROM v_latest_reconciliation").fetchone()
            if latest_recon is None:
                alerts.append({
                    "severity": "warning",
                    "category": "reconciliation",
                    "title": "Reconciliation has never been run",
                    "detail": "Run reconcile to verify budget categories match YNAB.",
                })
            elif latest_recon["status"] == "failed":
                alerts.append({
                    "severity": "critical",
                    "category": "reconciliation",
                    "title": f"Reconciliation failed with {latest_recon['mismatch_count']} mismatches",
                    "detail": "Budget categories don't match YNAB. Check mismatches in the summary.",
                })

            # Check budget import
            latest_import = conn.execute("SELECT * FROM v_latest_budget_import").fetchone()
            if latest_import is None:
                alerts.append({
                    "severity": "warning",
                    "category": "no_budget",
                    "title": "No budget has been imported",
                    "detail": "Run import_budget to load the baseline plan.",
                })

        # Check projection (only if we have data)
        try:
            projection = self.year_end_projection()
            totals = projection.get("totals", {})
            variance = totals.get("projected_variance_milliunits", 0)
            planned = totals.get("planned_annual_milliunits", 0)
            if planned and variance > 0:
                pct = round(variance / planned * 100, 1)
                if pct > 10:
                    alerts.append({
                        "severity": "critical",
                        "category": "projection",
                        "title": f"Projected {pct}% over annual budget",
                        "detail": f"Projected overage of ${variance // 1000} based on current run rate.",
                    })
                elif pct > 5:
                    alerts.append({
                        "severity": "warning",
                        "category": "projection",
                        "title": f"Projected {pct}% over annual budget",
                        "detail": f"Projected overage of ${variance // 1000}. Consider adjustments.",
                    })

            # Count over/under categories
            over_count = sum(1 for c in projection.get("categories", []) if c["projected_variance_milliunits"] > 5000 * 12)
            under_count = sum(1 for c in projection.get("categories", []) if c["projected_variance_milliunits"] < -5000 * 12)
        except Exception:
            over_count = under_count = 0
            projection = {"months_elapsed": 0}

        # Determine overall status
        severities = [a["severity"] for a in alerts]
        if "critical" in severities:
            overall = "critical"
        elif "warning" in severities:
            overall = "warning"
        else:
            overall = "healthy"

        # Sort alerts: critical first, then warning
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        alerts.sort(key=lambda a: severity_order.get(a["severity"], 99))

        return {
            "checked_at": utc_now(),
            "overall_status": overall,
            "alerts": alerts,
            "stats": {
                "categories_over_budget": over_count,
                "categories_under_budget": under_count,
                "projected_annual_variance_milliunits": projection.get("totals", {}).get("projected_variance_milliunits", 0) if isinstance(projection.get("totals"), dict) else 0,
                "months_of_data": projection.get("months_elapsed", 0),
            },
        }
