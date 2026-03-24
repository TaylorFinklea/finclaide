from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from finclaide.auth import require_bearer_token

analytics_api = Blueprint("analytics_api", __name__, url_prefix="/api/analytics")


def _container():
    return current_app.extensions["finclaide"]


@analytics_api.get("/compare")
@require_bearer_token
def compare():
    month_a = request.args.get("month_a")
    month_b = request.args.get("month_b")
    if not month_a or not month_b:
        return jsonify({"error": "month_a and month_b are required"}), 400
    return jsonify(_container().analytics.compare_months(month_a, month_b))


@analytics_api.get("/trends")
@require_bearer_token
def trends():
    months = int(request.args.get("months", "6"))
    return jsonify(
        _container().analytics.spending_trends(
            months=months,
            group_name=request.args.get("group"),
            category_name=request.args.get("category"),
            as_of_month=request.args.get("as_of_month"),
        )
    )


@analytics_api.get("/projection")
@require_bearer_token
def projection():
    return jsonify(
        _container().analytics.year_end_projection(
            as_of_month=request.args.get("as_of_month"),
        )
    )


@analytics_api.get("/anomalies")
@require_bearer_token
def anomalies():
    months = int(request.args.get("months", "3"))
    threshold = float(request.args.get("threshold", "2.0"))
    return jsonify(
        _container().analytics.detect_anomalies(
            months=months,
            threshold_sigma=threshold,
            as_of_month=request.args.get("as_of_month"),
        )
    )


@analytics_api.get("/recommendations")
@require_bearer_token
def recommendations():
    return jsonify(_container().analytics.budget_recommendations(as_of_month=request.args.get("as_of_month")))


@analytics_api.get("/aggregate")
@require_bearer_token
def aggregate():
    period = request.args.get("period", "quarter")
    return jsonify(
        _container().analytics.aggregate_spending(
            period=period,
            group_name=request.args.get("group"),
            category_name=request.args.get("category"),
        )
    )


@analytics_api.get("/health")
@require_bearer_token
def health():
    return jsonify(_container().analytics.financial_health_check())
