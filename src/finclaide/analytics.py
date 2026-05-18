from __future__ import annotations

import calendar
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from finclaide.category_filters import is_payment_flow_category
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


def _month_reference(month: str | None = None) -> date:
    if month:
        parsed = datetime.strptime(month, "%Y-%m").date()
        return date(parsed.year, parsed.month, 1)
    now = datetime.now(UTC).date()
    return date(now.year, now.month, 1)


def _next_month_start(reference: date) -> date:
    if reference.month == 12:
        return date(reference.year + 1, 1, 1)
    return date(reference.year, reference.month + 1, 1)


def _months_in_year(plan_year: int, through_month: int) -> list[str]:
    return [f"{plan_year:04d}-{m:02d}" for m in range(1, through_month + 1)]


def _stddev(values: list[int | float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _format_money_inline(milliunits: int) -> str:
    """Format milliunits as a compact dollar string for narrative copy
    (`$200`, `$1,250`, `$15.50`). Whole-dollar amounts drop the cents."""
    dollars = milliunits / 1000
    if abs(dollars) >= 100 and dollars == int(dollars):
        return f"${int(dollars):,}"
    if dollars == int(dollars):
        return f"${int(dollars):,}"
    return f"${dollars:,.2f}"


def _classify_pace(
    *,
    planned: int,
    actual: int,
    days_elapsed: int,
    days_total: int,
) -> tuple[float, str]:
    """Compute (pace_factor, pace_status) per the spec ladder.

    pace_factor = (actual / planned) / (days_elapsed / days_total)
    Sentinels: -1.0 = unplanned (planned=0, actual>0), 0.0 = no spend yet."""
    if planned == 0 and actual > 0:
        return -1.0, "unplanned"
    if actual == 0:
        return 0.0, "no_spend_yet"
    if planned == 0 or days_elapsed <= 0:
        return -1.0, "unplanned"
    pace = (actual / planned) / (days_elapsed / days_total)
    if pace < 0.85:
        return pace, "under_pace"
    if pace <= 1.15:
        return pace, "on_pace"
    if pace <= 1.50:
        return pace, "over_pace"
    if pace <= 2.00:
        return pace, "at_risk"
    return pace, "blowout"


# Phase 4: groups whose categories use plan-based projection ("the
# operator has explicit control"). Everything else is run-rate-based
# ("recent behavior predicts future better than aspirational plan").
# Hardcoded for v1; the operator iterates on this rule once they see
# live forecasts. See `_is_fixed_group` below.
_FIXED_GROUPS = frozenset({
    "Bills",
    "Payments",
    "Credit Card Payments",
    "Stipends",
    "Savings",
})


def _is_fixed_group(group_name: str) -> bool:
    """Hybrid forecast classifier — does this category project from
    plan or from recent run-rate?

    Fixed = plan is authoritative (rent, salary, fixed bills).
    Discretionary = recent behavior is more predictive (groceries,
    eating out).

    OPERATOR-EDITABLE: refine this rule once live forecasts are
    visible. The function is pure and small; tests in
    `tests/test_cashflow.py` cover the default classification."""
    return group_name in _FIXED_GROUPS


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    """Return (year, month) `delta` months after (year, month). delta=1
    advances to the next month; delta=12 advances a year."""
    total = year * 12 + (month - 1) + delta
    return divmod(total, 12)[0], divmod(total, 12)[1] + 1


def _month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


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
        as_of_month: str | None = None,
    ) -> dict[str, Any]:
        """Monthly spending time series with trend analysis."""
        reference = _month_reference(as_of_month)
        since = _n_months_ago(months, reference=reference)
        through = _next_month_start(reference).isoformat()
        conditions = ["t.deleted = 0", "t.date >= ?", "t.date < ?"]
        params: list[Any] = [f"{since}-01", through]
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
            "as_of_month": reference.strftime("%Y-%m"),
            "categories": categories,
        }

    # ------------------------------------------------------------------
    # month_pace
    # ------------------------------------------------------------------

    def month_pace(
        self,
        *,
        month: str | None = None,
        now: date | None = None,
    ) -> dict[str, Any]:
        """Per-category mid-month pace analysis.

        For each `monthly` and `stipends` category in the active plan,
        compares actual spending so far against a linear-pace budget
        (planned × days_elapsed / days_total). Returns a status ladder
        and projected month-end values; the frontend ranks by
        projected_overage_milliunits desc and surfaces the worst.

        `now` is overridable for tests; defaults to today (UTC).

        See `.docs/ai/phases/phase-3-decision-engine-spec.md` for the
        full status threshold ladder.
        """
        today = now or datetime.now(UTC).date()
        target_month_first = _month_reference(month)
        days_total = calendar.monthrange(
            target_month_first.year, target_month_first.month
        )[1]
        target_month_last = date(
            target_month_first.year,
            target_month_first.month,
            days_total,
        )

        # For past months we treat the entire month as elapsed; for the
        # current month we use today's day-of-month; for future months
        # we'd surface a "warming up" empty (days_elapsed = 0).
        if today >= target_month_last:
            days_elapsed = days_total
        elif today < target_month_first:
            days_elapsed = 0
        else:
            days_elapsed = today.day
        days_remaining = max(0, days_total - days_elapsed)

        warming_up = days_elapsed < 3

        month_label = target_month_first.strftime("%Y-%m")
        next_month_first = _next_month_start(target_month_first)

        if warming_up:
            return {
                "month": month_label,
                "days_elapsed": days_elapsed,
                "days_total": days_total,
                "days_remaining": days_remaining,
                "warming_up": True,
                "categories": [],
                "totals": {
                    "planned_milliunits": 0,
                    "actual_milliunits": 0,
                    "projected_month_end_milliunits": 0,
                },
            }

        with self.database.connect() as conn:
            planned_rows = conn.execute(
                """
                SELECT
                    pc.id AS category_id,
                    pc.group_name,
                    pc.category_name,
                    pc.block,
                    pc.planned_milliunits
                FROM plan_categories pc
                JOIN plans p ON p.id = pc.plan_id
                WHERE p.status = 'active'
                  AND pc.block IN ('monthly', 'stipends')
                """
            ).fetchall()

            actual_rows = conn.execute(
                """
                SELECT
                    COALESCE(c.group_name, t.group_name) AS group_name,
                    COALESCE(c.name, t.category_name) AS category_name,
                    SUM(CASE WHEN t.amount_milliunits < 0
                             THEN -1 * t.amount_milliunits ELSE 0 END) AS spend_milliunits
                FROM transactions t
                LEFT JOIN categories c ON c.id = t.category_id
                WHERE t.deleted = 0
                  AND t.date >= ?
                  AND t.date < ?
                GROUP BY 1, 2
                """,
                (target_month_first.isoformat(), next_month_first.isoformat()),
            ).fetchall()

        actual_by_key = {
            (row["group_name"] or "", row["category_name"] or ""): int(row["spend_milliunits"])
            for row in actual_rows
        }

        category_rows: list[dict[str, Any]] = []
        total_planned = 0
        total_actual = 0
        total_projected = 0
        for row in planned_rows:
            planned = int(row["planned_milliunits"] or 0)
            key = (row["group_name"] or "", row["category_name"] or "")
            actual = actual_by_key.get(key, 0)

            pace_factor, pace_status = _classify_pace(
                planned=planned,
                actual=actual,
                days_elapsed=days_elapsed,
                days_total=days_total,
            )
            if days_elapsed > 0 and actual > 0:
                projected = round(actual * days_total / days_elapsed)
            else:
                projected = max(actual, planned)
            projected_overage = projected - planned

            category_rows.append(
                {
                    "category_id": int(row["category_id"]),
                    "group_name": row["group_name"],
                    "category_name": row["category_name"],
                    "block": row["block"],
                    "planned_milliunits": planned,
                    "actual_milliunits": actual,
                    "pace_factor": pace_factor,
                    "pace_status": pace_status,
                    "projected_month_end_milliunits": projected,
                    "projected_overage_milliunits": projected_overage,
                }
            )
            total_planned += planned
            total_actual += actual
            total_projected += projected

        category_rows.sort(
            key=lambda r: r["projected_overage_milliunits"],
            reverse=True,
        )

        return {
            "month": month_label,
            "days_elapsed": days_elapsed,
            "days_total": days_total,
            "days_remaining": days_remaining,
            "warming_up": False,
            "categories": category_rows,
            "totals": {
                "planned_milliunits": total_planned,
                "actual_milliunits": total_actual,
                "projected_month_end_milliunits": total_projected,
            },
        }

    # ------------------------------------------------------------------
    # cash_flow_timeline (Phase 4 Slice 1)
    # ------------------------------------------------------------------

    def cash_flow_timeline(
        self,
        *,
        months: int = 12,
        as_of_month: str | None = None,
        starting_balance_override_milliunits: int | None = None,
    ) -> dict[str, Any]:
        """12-month forward cash-flow projection. See plan file
        (`.docs/ai/phases/...`-style docs) for the model.

        Hybrid: fixed groups (`Bills`, `Payments`, `Credit Card Payments`,
        `Stipends`, `Savings`) project from plan. Discretionary
        categories project from 6-month run-rate (falling back to plan
        if no recent transactions). Annual + one_time categories
        with `due_month` set lump in that month; otherwise smoothed
        across 12 months.

        Stipends are inflows. Bills/Payments/Savings/discretionary +
        obligation lumps are outflows."""
        reference = _month_reference(as_of_month)
        as_of_label = reference.strftime("%Y-%m")
        # Build the 12-month window starting from `reference`.
        month_keys: list[str] = []
        year, month = reference.year, reference.month
        for offset in range(months):
            y, m = _add_months(year, month, offset)
            month_keys.append(_month_key(y, m))

        starting_balance = (
            starting_balance_override_milliunits
            if starting_balance_override_milliunits is not None
            else self._cash_starting_balance()
        )

        # Pull the active plan + run-rate per category once.
        with self.database.connect() as conn:
            plan_rows = conn.execute(
                """
                SELECT pc.id, pc.group_name, pc.category_name, pc.block,
                       pc.planned_milliunits, pc.annual_target_milliunits,
                       pc.due_month
                FROM plan_categories pc
                JOIN plans p ON p.id = pc.plan_id
                WHERE p.status = 'active'
                """
            ).fetchall()
        run_rates = self._six_month_run_rates(reference)

        # Per-month accumulators.
        per_month_inflows = [0] * months
        per_month_outflows = [0] * months
        per_month_lumps: list[list[dict[str, Any]]] = [[] for _ in range(months)]
        # category total contribution (signed: positive = outflow, negative = inflow)
        # only used for shortfall_drivers ranking.
        per_month_top_contribs: list[list[dict[str, Any]]] = [[] for _ in range(months)]
        # Cumulative outflow per category up through each month (for shortfall_drivers).
        cumulative_by_category: dict[tuple[str, str], list[int]] = {}

        for row in plan_rows:
            grp = row["group_name"] or ""
            name = row["category_name"] or ""
            block = row["block"]
            planned = int(row["planned_milliunits"] or 0)
            annual_target = int(row["annual_target_milliunits"] or 0)
            due_month = row["due_month"]
            cat_key = (grp, name)
            cumulative_by_category.setdefault(cat_key, [0] * months)

            if block in ("annual", "one_time"):
                # Lump in due_month (current or next year, whichever
                # falls within the window) OR smoothed if no due_month.
                lump_amount = annual_target or (planned * 12)
                if due_month is not None:
                    # Find the month index in the window matching due_month.
                    target_index = None
                    for idx, key in enumerate(month_keys):
                        m = int(key.split("-")[1])
                        if m == int(due_month):
                            target_index = idx
                            break
                    if target_index is not None and lump_amount > 0:
                        per_month_outflows[target_index] += lump_amount
                        per_month_lumps[target_index].append({
                            "group_name": grp,
                            "category_name": name,
                            "milliunits": lump_amount,
                        })
                        per_month_top_contribs[target_index].append({
                            "group_name": grp,
                            "category_name": name,
                            "milliunits": lump_amount,
                            "basis": "lump",
                        })
                        cumulative_by_category[cat_key][target_index] += lump_amount
                else:
                    # Smooth across the 12 months.
                    monthly_share = lump_amount // 12 if lump_amount else 0
                    if monthly_share > 0:
                        for idx in range(months):
                            per_month_outflows[idx] += monthly_share
                            per_month_top_contribs[idx].append({
                                "group_name": grp,
                                "category_name": name,
                                "milliunits": monthly_share,
                                "basis": "plan",
                            })
                            cumulative_by_category[cat_key][idx] += monthly_share
                continue

            # monthly / stipends / savings — recurring each month.
            is_fixed = _is_fixed_group(grp)
            if is_fixed:
                amount = planned
                basis = "plan"
            else:
                rate = run_rates.get(cat_key)
                if rate is None:
                    amount = planned
                    basis = "plan"
                else:
                    amount = rate
                    basis = "run_rate"

            if amount <= 0:
                continue

            for idx in range(months):
                if block == "stipends":
                    per_month_inflows[idx] += amount
                    per_month_top_contribs[idx].append({
                        "group_name": grp,
                        "category_name": name,
                        "milliunits": -amount,  # signed: inflow = negative outflow
                        "basis": basis,
                    })
                else:
                    per_month_outflows[idx] += amount
                    per_month_top_contribs[idx].append({
                        "group_name": grp,
                        "category_name": name,
                        "milliunits": amount,
                        "basis": basis,
                    })
                    cumulative_by_category[cat_key][idx] += amount

        # Build per-month payload + balance trajectory.
        balance = starting_balance
        months_payload: list[dict[str, Any]] = []
        lowest_balance_value = balance
        lowest_balance_month = month_keys[0] if month_keys else as_of_label
        first_negative_month: str | None = None
        for idx, key in enumerate(month_keys):
            inflow = per_month_inflows[idx]
            outflow = per_month_outflows[idx]
            net = inflow - outflow
            balance += net
            top_outflows = sorted(
                (c for c in per_month_top_contribs[idx] if c["milliunits"] > 0),
                key=lambda c: c["milliunits"],
                reverse=True,
            )[:3]
            months_payload.append(
                {
                    "month": key,
                    "inflows_milliunits": inflow,
                    "outflows_milliunits": outflow,
                    "obligation_lumps": per_month_lumps[idx],
                    "top_outflow_categories": top_outflows,
                    "net_milliunits": net,
                    "ending_balance_milliunits": balance,
                }
            )
            if balance < lowest_balance_value:
                lowest_balance_value = balance
                lowest_balance_month = key
            if first_negative_month is None and balance < 0:
                first_negative_month = key

        shortfall_drivers: list[dict[str, Any]] | None = None
        if first_negative_month is not None:
            negative_idx = month_keys.index(first_negative_month)
            totals = []
            for (grp, name), cumulative in cumulative_by_category.items():
                cum_total = sum(cumulative[: negative_idx + 1])
                if cum_total > 0:
                    totals.append(
                        {
                            "group_name": grp,
                            "category_name": name,
                            "total_milliunits": cum_total,
                        }
                    )
            totals.sort(key=lambda d: d["total_milliunits"], reverse=True)
            shortfall_drivers = totals[:3]

        return {
            "as_of_month": as_of_label,
            "months_ahead": months,
            "starting_balance_milliunits": starting_balance,
            "months": months_payload,
            "lowest_balance": {
                "month": lowest_balance_month,
                "balance_milliunits": lowest_balance_value,
            },
            "first_negative_month": first_negative_month,
            "shortfall_drivers": shortfall_drivers,
        }

    # ------------------------------------------------------------------
    # cash_flow_recommendations (Phase 4 Slice 2)
    # ------------------------------------------------------------------

    def cash_flow_recommendations(
        self,
        *,
        months: int = 12,
        as_of_month: str | None = None,
    ) -> dict[str, Any]:
        """Plan-calibration recommendations: discretionary categories
        whose 6-month run-rate exceeds plan by ≥10% and ≥$25/mo. Each
        carries a projected impact (lowest_balance + first_negative_month
        deltas) so the operator can pick the highest-leverage tweaks."""
        baseline = self.cash_flow_timeline(months=months, as_of_month=as_of_month)
        baseline_lowest = baseline["lowest_balance"]["balance_milliunits"]
        baseline_first_neg = baseline["first_negative_month"]
        starting_balance = baseline["starting_balance_milliunits"]
        baseline_months = baseline["months"]
        as_of_label = baseline["as_of_month"]

        reference = _month_reference(as_of_month)
        with self.database.connect() as conn:
            plan_rows = conn.execute(
                """
                SELECT pc.id, pc.group_name, pc.category_name, pc.block,
                       pc.planned_milliunits
                FROM plan_categories pc
                JOIN plans p ON p.id = pc.plan_id
                WHERE p.status = 'active' AND pc.block IN ('monthly', 'stipends')
                """
            ).fetchall()
        run_rates = self._six_month_run_rates(reference)

        recommendations: list[dict[str, Any]] = []
        for row in plan_rows:
            grp = row["group_name"] or ""
            name = row["category_name"] or ""
            block = row["block"]
            planned = int(row["planned_milliunits"] or 0)
            cat_id = int(row["id"])

            # Calibration only applies to discretionary categories. The
            # operator's plan is authoritative for fixed groups.
            if _is_fixed_group(grp):
                continue

            rate = run_rates.get((grp, name))
            if rate is None:
                continue

            # Trigger: run-rate exceeds plan by ≥10% AND absolute monthly
            # delta ≥ $25 (matches the pace card's noise floor).
            monthly_delta = rate - planned
            if monthly_delta < 25_000:
                continue
            if planned > 0 and rate < planned * 1.10:
                continue
            # Round suggested amount to whole dollars.
            suggested = round(rate / 1000) * 1000
            if suggested == planned:
                continue

            applied_delta = suggested - planned

            # Cheap simulation: clone baseline contributions, add the
            # delta to each month's outflow (or subtract from inflow if
            # this is a stipends category — though stipends are fixed,
            # so we won't reach here in practice).
            sim_months = []
            running_balance = starting_balance
            sim_lowest = running_balance
            sim_lowest_month = baseline_months[0]["month"] if baseline_months else as_of_label
            sim_first_neg: str | None = None
            for base in baseline_months:
                if block == "stipends":
                    sim_inflows = base["inflows_milliunits"] + applied_delta
                    sim_outflows = base["outflows_milliunits"]
                else:
                    sim_inflows = base["inflows_milliunits"]
                    sim_outflows = base["outflows_milliunits"] + applied_delta
                sim_net = sim_inflows - sim_outflows
                running_balance += sim_net
                sim_months.append({
                    "month": base["month"],
                    "ending_balance": running_balance,
                })
                if running_balance < sim_lowest:
                    sim_lowest = running_balance
                    sim_lowest_month = base["month"]
                if sim_first_neg is None and running_balance < 0:
                    sim_first_neg = base["month"]

            # Build copy
            current_dollars = planned // 1000
            suggested_dollars = suggested // 1000
            rate_dollars = rate // 1000
            headline = (
                f"{grp} / {name}: averaging ${rate_dollars}/mo against "
                f"${current_dollars} plan. Raise plan to ${suggested_dollars}."
            )
            rationale_parts = [
                f"6-month run-rate is ${rate_dollars}/mo, "
                f"{int((rate / max(planned, 1) - 1) * 100) if planned else 0}% over the "
                f"${current_dollars}/mo plan." if planned > 0 else
                f"6-month run-rate is ${rate_dollars}/mo with no plan currently set.",
            ]
            if baseline_first_neg and sim_first_neg != baseline_first_neg:
                if sim_first_neg is None:
                    rationale_parts.append(
                        f"Forecast no longer goes negative within {months} months."
                    )
                else:
                    rationale_parts.append(
                        f"Pushes first-negative month from {baseline_first_neg} to {sim_first_neg}."
                    )
            elif baseline_lowest != sim_lowest:
                rationale_parts.append(
                    f"Lowest-balance moves by "
                    f"${(sim_lowest - baseline_lowest) // 1000:+,}/."
                )

            recommendations.append({
                "kind": "plan_calibration",
                "category": {
                    "id": cat_id,
                    "group_name": grp,
                    "category_name": name,
                    "block": block,
                },
                "current_planned_milliunits": planned,
                "suggested_planned_milliunits": suggested,
                "run_rate_milliunits": rate,
                "monthly_delta_milliunits": applied_delta,
                "annual_impact_milliunits": applied_delta * 12,
                "headline": headline,
                "rationale": " ".join(rationale_parts),
                "projected_impact": {
                    "lowest_balance_before_milliunits": baseline_lowest,
                    "lowest_balance_after_milliunits": sim_lowest,
                    "first_negative_month_before": baseline_first_neg,
                    "first_negative_month_after": sim_first_neg,
                },
            })

        # Sort: biggest improvement to lowest_balance first; tiebreak by
        # absolute monthly delta. (Note: applying a calibration
        # *increases* outflow, so it makes the forecast WORSE, not
        # better. The "improvement" framing is — these are the
        # categories where the plan is most out of alignment with reality;
        # higher delta = bigger gap = bigger leverage to fix.)
        recommendations.sort(
            key=lambda r: (
                abs(r["monthly_delta_milliunits"]),
            ),
            reverse=True,
        )
        return {
            "as_of_month": as_of_label,
            "baseline_lowest_balance_milliunits": baseline_lowest,
            "baseline_first_negative_month": baseline_first_neg,
            "recommendations": recommendations[:10],
        }

    def cash_flow_rebalance_prompts(
        self,
        *,
        months: int = 12,
        as_of_month: str | None = None,
    ) -> dict[str, Any]:
        """Pair every calibration rec that would push the cascade leftover
        below zero with a compensating decrease drawn from a cushion
        category. Also surface a standalone 'cascade currently red' prompt
        when the operator's hand-edited plan is itself unbalanced.

        Outputs prompts shaped for the UI:
            kind: 'rec_paired' | 'cascade_deficit'
            increase: {category_id, group, name, current_milli, suggested_milli, delta_milli} | None
            decrease: same shape | None
            delta_milli: int (absolute amount being moved)
            rationale: str
            cushion_status: 'found' | 'none_available'

        Cushion picker order:
          1) `savings` block outflow with planned >= delta (largest first).
          2) Discretionary `monthly` outflow whose 6-month run-rate is at
             least delta + $25 below its plan (slack proven by actuals).
          3) Otherwise emit the prompt with cushion=None and
             cushion_status='none_available' — never guess.

        Tithe-linked rows (`tithe_percent IS NOT NULL`) and rows in fixed
        groups are off-limits as cushions to avoid silently editing
        formula-driven or operator-authoritative amounts (excluding the
        savings block, which is the cushion *by design*).
        """
        rec_payload = self.cash_flow_recommendations(
            months=months,
            as_of_month=as_of_month,
        )
        as_of_label = rec_payload["as_of_month"]
        recs = rec_payload["recommendations"]

        with self.database.connect() as conn:
            cascade_leftover = self._compute_cascade_leftover(conn)
            cushion_rows = conn.execute(
                """
                SELECT pc.id, pc.group_name, pc.category_name, pc.block,
                       pc.planned_milliunits, pc.tithe_percent
                FROM plan_categories pc
                JOIN plans p ON p.id = pc.plan_id
                WHERE p.status = 'active'
                  AND pc.kind = 'outflow'
                  AND pc.tithe_percent IS NULL
                """
            ).fetchall()

        reference = _month_reference(as_of_month)
        run_rates = self._six_month_run_rates(reference)

        # Pre-bucket cushion candidates so each prompt picks deterministically
        # without re-scanning the plan. Order within each bucket is by
        # planned amount descending (savings) or by slack descending
        # (discretionary) so the largest cushion goes first.
        savings_pool: list[dict[str, Any]] = []
        slack_pool: list[dict[str, Any]] = []
        for row in cushion_rows:
            grp = row["group_name"] or ""
            name = row["category_name"] or ""
            block = row["block"]
            planned = int(row["planned_milliunits"] or 0)
            entry = {
                "id": int(row["id"]),
                "group_name": grp,
                "category_name": name,
                "block": block,
                "planned_milliunits": planned,
            }
            if block == "savings" and planned > 0:
                savings_pool.append(entry)
                continue
            if block == "monthly" and not _is_fixed_group(grp):
                rate = run_rates.get((grp, name))
                if rate is None:
                    continue
                slack = planned - rate
                if slack <= 0:
                    continue
                entry["slack_milliunits"] = slack
                slack_pool.append(entry)
        savings_pool.sort(
            key=lambda e: e["planned_milliunits"], reverse=True
        )
        slack_pool.sort(
            key=lambda e: e["slack_milliunits"], reverse=True
        )

        def _make_cushion(
            entry: dict[str, Any],
            delta_milli: int,
            source: str,
            available: int,
        ) -> dict[str, Any]:
            applied = min(delta_milli, available)
            return {
                "category_id": entry["id"],
                "group_name": entry["group_name"],
                "category_name": entry["category_name"],
                "block": entry["block"],
                "current_milli": entry["planned_milliunits"],
                "suggested_milli": entry["planned_milliunits"] - applied,
                "delta_milli": -applied,
                "source": source,
                "covers_full_delta": applied >= delta_milli,
            }

        def pick_cushion(delta_milli: int) -> dict[str, Any] | None:
            # Prefer the smallest savings row that fully covers the delta —
            # drains a single cushion rather than overspending the largest.
            full_savings = [
                e for e in savings_pool if e["planned_milliunits"] >= delta_milli
            ]
            if full_savings:
                pick = min(full_savings, key=lambda e: e["planned_milliunits"])
                return _make_cushion(
                    pick, delta_milli, "savings", pick["planned_milliunits"]
                )
            # Same logic for slack discretionary.
            full_slack = [
                e for e in slack_pool
                if e["slack_milliunits"] >= delta_milli + 25_000
            ]
            if full_slack:
                pick = min(full_slack, key=lambda e: e["slack_milliunits"])
                return _make_cushion(
                    pick, delta_milli, "slack", pick["planned_milliunits"]
                )
            # Partial fill: no single cushion fully covers; pick the
            # biggest savings (or slack as fallback) so the operator
            # makes the largest dent in one click and finishes manually.
            if savings_pool:
                pick = savings_pool[0]
                return _make_cushion(
                    pick, delta_milli, "savings", pick["planned_milliunits"]
                )
            if slack_pool:
                pick = slack_pool[0]
                # Apply at most the proven slack so we don't push the row
                # below its run-rate.
                return _make_cushion(
                    pick, delta_milli, "slack", pick["slack_milliunits"]
                )
            return None

        prompts: list[dict[str, Any]] = []

        # (a) Calibration recs that would tip the cascade negative on apply.
        for rec in recs:
            delta = int(rec["monthly_delta_milliunits"])
            if delta <= 0:
                continue
            if cascade_leftover - delta >= 0:
                # Calibration alone keeps us positive — surface as a normal
                # rec via the existing endpoint, not as a rebalance.
                continue
            increase = {
                "category_id": rec["category"]["id"],
                "group_name": rec["category"]["group_name"],
                "category_name": rec["category"]["category_name"],
                "block": rec["category"]["block"],
                "current_milli": int(rec["current_planned_milliunits"]),
                "suggested_milli": int(rec["suggested_planned_milliunits"]),
                "delta_milli": delta,
            }
            cushion = pick_cushion(delta)
            rationale = self._rebalance_rationale(
                increase=increase,
                cushion=cushion,
                deficit_after_increase=delta - max(cascade_leftover, 0),
            )
            prompts.append({
                "kind": "rec_paired",
                "increase": increase,
                "decrease": cushion,
                "delta_milli": delta,
                "rationale": rationale,
                "cushion_status": "found" if cushion else "none_available",
            })

        # (b) Standalone deficit prompt — cascade is red right now from a
        # hand-edited plan, no rec involved.
        if cascade_leftover < -1000:
            deficit = -cascade_leftover
            cushion = pick_cushion(deficit)
            rationale = (
                f"Plan currently exceeds inflow by ${deficit / 1000:,.2f}/mo. "
                f"{'Pull from ' + cushion['category_name'] + ' to balance.' if cushion else 'No automatic cushion available.'}"
            )
            prompts.append({
                "kind": "cascade_deficit",
                "increase": None,
                "decrease": cushion,
                "delta_milli": deficit,
                "rationale": rationale,
                "cushion_status": "found" if cushion else "none_available",
            })

        return {
            "as_of_month": as_of_label,
            "cascade_leftover_milliunits": cascade_leftover,
            "prompts": prompts,
        }

    def _compute_cascade_leftover(self, connection) -> int:
        """Server-side mirror of the JS cascade math: total inflow minus
        total outflow on the active plan, in milliunits. Centralizes the
        math so frontend and rebalance prompts agree to the milliunit."""
        row = connection.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN pc.kind = 'inflow'
                                  THEN pc.planned_milliunits ELSE 0 END), 0)
                  AS inflow,
                COALESCE(SUM(CASE WHEN pc.kind = 'outflow'
                                  THEN pc.planned_milliunits ELSE 0 END), 0)
                  AS outflow
            FROM plan_categories pc
            JOIN plans p ON p.id = pc.plan_id
            WHERE p.status = 'active'
            """
        ).fetchone()
        if row is None:
            return 0
        return int(row["inflow"] or 0) - int(row["outflow"] or 0)

    @staticmethod
    def _rebalance_rationale(
        *,
        increase: dict[str, Any],
        cushion: dict[str, Any] | None,
        deficit_after_increase: int,
    ) -> str:
        delta_dollars = increase["delta_milli"] / 1000
        category = f"{increase['group_name']} / {increase['category_name']}"
        if cushion is None:
            return (
                f"Raising {category} by ${delta_dollars:+,.2f}/mo would push the "
                f"cascade ${deficit_after_increase / 1000:,.2f}/mo negative. "
                f"No automatic cushion available — adjust manually."
            )
        cushion_label = (
            f"{cushion['category_name']} (savings)"
            if cushion["source"] == "savings"
            else f"{cushion['category_name']} (running below plan)"
        )
        if cushion.get("covers_full_delta"):
            return (
                f"Raising {category} by ${delta_dollars:+,.2f}/mo; "
                f"pull the same amount from {cushion_label} to keep the cascade balanced."
            )
        applied_dollars = -cushion["delta_milli"] / 1000
        return (
            f"Raising {category} by ${delta_dollars:+,.2f}/mo. "
            f"{cushion_label} can only absorb ${applied_dollars:,.2f}/mo — "
            f"applying covers part of the gap; close the rest manually."
        )

    def runway(self, *, months_window: int = 6, as_of_month: str | None = None) -> dict[str, Any]:
        """Cash on hand divided by trailing average monthly outflow.

        Both halves come from the same data we already trust:
          * cash on hand is `_cash_starting_balance()` — positive account
            balances on open, on-budget YNAB accounts.
          * monthly burn is the trailing-N-month outflow average from the
            cash-flow timeline, excluding the current (partial) month.

        Returns 0 runway months when cash is non-positive; returns a sentinel
        (None) when burn is 0 or there isn't enough history yet to average.
        """
        reference = _month_reference(as_of_month)
        cash = self._cash_starting_balance()
        # Pull the timeline backward: the cash_flow_timeline() helper projects
        # forward, but for runway we want trailing actuals. Sum negative
        # transaction amounts directly per month and average.
        since = _n_months_ago(months_window, reference=reference)
        through = reference.isoformat()  # exclusive upper bound (start of current month)
        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    substr(t.date, 1, 7) AS month_key,
                    SUM(CASE WHEN t.amount_milliunits < 0
                             THEN -1 * t.amount_milliunits ELSE 0 END) AS outflow
                FROM transactions t
                WHERE t.date >= ? AND t.date < ?
                GROUP BY month_key
                """,
                (f"{since}-01", through),
            ).fetchall()
        monthly_outflows = [int(r["outflow"] or 0) for r in rows if r["outflow"]]
        if not monthly_outflows:
            return {
                "cash_milliunits": cash,
                "monthly_burn_milliunits": 0,
                "runway_months": None,
                "trail_months": 0,
                "as_of_month": reference.strftime("%Y-%m"),
            }
        monthly_burn = sum(monthly_outflows) // len(monthly_outflows)
        runway_months: float | None
        if monthly_burn <= 0:
            runway_months = None
        elif cash <= 0:
            runway_months = 0.0
        else:
            runway_months = round(cash / monthly_burn, 1)
        return {
            "cash_milliunits": cash,
            "monthly_burn_milliunits": monthly_burn,
            "runway_months": runway_months,
            "trail_months": len(monthly_outflows),
            "as_of_month": reference.strftime("%Y-%m"),
        }

    def _cash_starting_balance(self) -> int:
        """Sum of positive account balances on open, on-budget accounts.
        Credit-card accounts in YNAB typically carry negative balances
        (liabilities) and are excluded by the `> 0` filter; closed
        accounts are skipped via `closed = 0`. Refine if operator data
        surfaces false positives."""
        with self.database.connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(balance_milliunits), 0) AS total
                FROM accounts
                WHERE closed = 0 AND balance_milliunits > 0
                """
            ).fetchone()
        return int(row["total"] or 0) if row else 0

    def _six_month_run_rates(self, reference: date) -> dict[tuple[str, str], int]:
        """Returns {(group, category): avg_milliunits_per_month} computed
        from the last 6 fully-elapsed months ending the month before
        `reference`. Only positive run-rates are returned."""
        since = _n_months_ago(6, reference=reference)
        through = reference.isoformat()
        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(c.group_name, t.group_name) AS group_name,
                    COALESCE(c.name, t.category_name) AS category_name,
                    SUM(CASE WHEN t.amount_milliunits < 0
                             THEN -1 * t.amount_milliunits ELSE 0 END) AS spend
                FROM transactions t
                LEFT JOIN categories c ON c.id = t.category_id
                WHERE t.deleted = 0
                  AND t.date >= ? AND t.date < ?
                GROUP BY 1, 2
                """,
                (f"{since}-01", through),
            ).fetchall()
        rates: dict[tuple[str, str], int] = {}
        for row in rows:
            grp = row["group_name"] or ""
            name = row["category_name"] or ""
            avg = int(row["spend"] or 0) // 6
            if avg > 0:
                rates[(grp, name)] = avg
        return rates

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
                "block": row["block"],
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
        as_of_month: str | None = None,
    ) -> dict[str, Any]:
        """Find unusual transactions and category-level spending spikes."""
        reference = _month_reference(as_of_month)
        since = f"{_n_months_ago(months, reference=reference)}-01"
        through = _next_month_start(reference).isoformat()

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
                  AND t.date < ?
                  AND t.amount_milliunits < 0
                ORDER BY group_name, category_name, t.date
                """,
                (since, through),
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
                  AND t.date < ?
                GROUP BY 1, 2, 3
                """,
                (since, through),
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
                    payee_count = sum(
                        1 for other in txns if other["payee_name"] == txn["payee_name"]
                    )
                    typical_low = int(max(0, mean - std))
                    typical_high = int(mean + std)
                    ratio = (txn["abs_amount"] / mean) if mean > 0 else 0
                    headline = (
                        f"{_format_money_inline(txn['abs_amount'])} is "
                        f"{round(sigma, 1)}σ above the typical "
                        f"{_format_money_inline(typical_low)}-"
                        f"{_format_money_inline(typical_high)} range "
                        f"for {grp or 'Uncategorized'} / {cat or 'Uncategorized'}."
                    )
                    context = (
                        f"Last {months} months of "
                        f"{cat or 'this category'} averaged "
                        f"{_format_money_inline(int(mean))}"
                    )
                    if ratio >= 1.5:
                        context += f"; this transaction is {ratio:.1f}× larger."
                    else:
                        context += "."
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
                        "narrative": {
                            "typical_low_milliunits": typical_low,
                            "typical_high_milliunits": typical_high,
                            "category_average_milliunits": int(mean),
                            "category_payee_count": payee_count,
                            "headline": headline,
                            "context": context,
                        },
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
                    typical_low = int(max(0, mean - std))
                    typical_high = int(mean + std)
                    other_months = [
                        m for m in monthly if m["month"] != entry["month"]
                    ]
                    other_months.sort(key=lambda m: m["month"], reverse=True)
                    recent = other_months[:3]
                    headline = (
                        f"{grp or 'Uncategorized'} / {cat or 'Uncategorized'} "
                        f"spent {_format_money_inline(entry['spend_milliunits'])} "
                        f"in {entry['month']} vs typical "
                        f"{_format_money_inline(typical_low)}-"
                        f"{_format_money_inline(typical_high)}."
                    )
                    if recent:
                        recent_str = ", ".join(
                            f"{m['month']} {_format_money_inline(m['spend_milliunits'])}"
                            for m in recent
                        )
                        context = f"Most recent comparable months: {recent_str}."
                    else:
                        context = "No prior months in the lookback window."
                    category_anomalies.append({
                        "group_name": grp,
                        "category_name": cat,
                        "month": entry["month"],
                        "spend_milliunits": entry["spend_milliunits"],
                        "historical_mean_milliunits": int(mean),
                        "historical_stddev_milliunits": int(std),
                        "sigma_distance": round(sigma, 1),
                        "narrative": {
                            "typical_low_milliunits": typical_low,
                            "typical_high_milliunits": typical_high,
                            "category_average_milliunits": int(mean),
                            "recent_months": recent,
                            "headline": headline,
                            "context": context,
                        },
                    })

        return {
            "lookback_months": months,
            "as_of_month": reference.strftime("%Y-%m"),
            "threshold_sigma": threshold_sigma,
            "transaction_anomalies": sorted(transaction_anomalies, key=lambda a: -a["sigma_distance"]),
            "category_anomalies": sorted(category_anomalies, key=lambda a: -a["sigma_distance"]),
        }

    # ------------------------------------------------------------------
    # budget_recommendations
    # ------------------------------------------------------------------

    def budget_recommendations(self, as_of_month: str | None = None) -> dict[str, Any]:
        """Concrete budget adjustment suggestions based on actual spending."""
        current = as_of_month or _current_month_label()
        projection = self.year_end_projection(current)
        trends = self.spending_trends(months=6, as_of_month=current)

        # Build trend lookup
        trend_lookup: dict[tuple[str, str], dict[str, Any]] = {}
        for cat in trends["categories"]:
            trend_lookup[(cat["group_name"], cat["category_name"])] = cat

        recommendations = []
        for cat in projection.get("categories", []):
            if is_payment_flow_category(cat["group_name"], cat["category_name"]):
                continue
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
                if self._is_accumulated_fixed_category_covered(
                    group_name=cat["group_name"],
                    block=cat.get("block"),
                    planned_monthly=planned,
                    actual_ytd=int(cat.get("actual_ytd_milliunits") or 0),
                    as_of_month=current,
                ):
                    continue
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

            evidence = self._recommendation_evidence(
                group_name=cat["group_name"],
                category_name=cat["category_name"],
                planned_monthly=planned,
                trend_info=trend_info,
                action=action,
            )

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
                "supporting_evidence": evidence,
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

    def _is_accumulated_fixed_category_covered(
        self,
        *,
        group_name: str | None,
        block: str | None,
        planned_monthly: int,
        actual_ytd: int,
        as_of_month: str,
    ) -> bool:
        """True when a lumpy fixed-category payment is covered by accrued plan.

        Some fixed categories behave like sinking funds: a monthly amount
        accumulates, then the real payment happens every few months. In that
        case one large payment month should not imply the monthly budget should
        be raised.
        """
        if block != "monthly" or planned_monthly <= 0:
            return False
        if not _is_fixed_group(group_name or ""):
            return False
        month_number = int(as_of_month.split("-")[1])
        accumulated_plan = planned_monthly * month_number
        return actual_ytd <= accumulated_plan

    def _recommendation_evidence(
        self,
        *,
        group_name: str,
        category_name: str,
        planned_monthly: int,
        trend_info: dict[str, Any],
        action: str,
    ) -> dict[str, Any]:
        """Slice 4: ground each recommendation with concrete months + transactions.

        Returns:
            recent_overage_months: list of {month, spend_milliunits, variance_milliunits}
                (descending by absolute variance) for months where actual differed
                from plan in the direction of the recommendation.
            top_transactions: largest 5 transactions in the lookback window.
        """
        monthly_spend = trend_info.get("months") or []
        recent_overage: list[dict[str, Any]] = []
        for m in monthly_spend:
            spend = int(m.get("spend_milliunits", 0))
            variance = spend - planned_monthly
            if action == "increase_budget" and variance > 0:
                recent_overage.append({
                    "month": m["month"],
                    "spend_milliunits": spend,
                    "variance_milliunits": variance,
                })
            elif action == "reduce_budget" and variance < 0:
                recent_overage.append({
                    "month": m["month"],
                    "spend_milliunits": spend,
                    "variance_milliunits": variance,
                })
        recent_overage.sort(
            key=lambda entry: abs(entry["variance_milliunits"]), reverse=True
        )

        with self.database.connect() as conn:
            txn_rows = conn.execute(
                """
                SELECT t.id, t.date, t.payee_name, t.amount_milliunits
                FROM transactions t
                LEFT JOIN categories c ON c.id = t.category_id
                WHERE t.deleted = 0
                  AND COALESCE(c.group_name, t.group_name) = ?
                  AND COALESCE(c.name, t.category_name) = ?
                  AND t.amount_milliunits < 0
                ORDER BY ABS(t.amount_milliunits) DESC
                LIMIT 5
                """,
                (group_name, category_name),
            ).fetchall()

        top_transactions = [
            {
                "id": row["id"],
                "date": row["date"],
                "payee_name": row["payee_name"],
                "amount_milliunits": int(row["amount_milliunits"]),
            }
            for row in txn_rows
        ]

        return {
            "recent_overage_months": recent_overage[:6],
            "top_transactions": top_transactions,
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
