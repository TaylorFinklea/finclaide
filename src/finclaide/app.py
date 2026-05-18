from __future__ import annotations

import httpx
from flask import Flask, jsonify

from finclaide.ai import AIService
from finclaide.analytics import AnalyticsService
from finclaide.analytics_api import analytics_api
from finclaide.api import api, register_error_handlers
from finclaide.budget_sheet import BudgetImporter
from finclaide.budget_source import create_budget_workbook_source
from finclaide.config import AppConfig
from finclaide.database import Database
from finclaide.export_storage import ExportStorage
from finclaide.frontend import register_frontend
from finclaide.locking import OperationLock
from finclaide.plan_exporter import PlanExporter
from finclaide.plan_service import PlanService
from finclaide.scheduled_refresh import ScheduledRefreshService
from finclaide.sheets_publisher import create_sheets_publisher
from finclaide.services import ReconciliationService, ReportService, ServiceContainer, WeeklyReviewService
from finclaide.ui_api import ui_api
from finclaide.ynab import YNABClient, YNABSyncService


def create_app(
    config_overrides: dict | None = None,
    *,
    ynab_transport: httpx.BaseTransport | None = None,
    budget_transport: httpx.BaseTransport | None = None,
    budget_access_token_provider=None,
) -> Flask:
    config = AppConfig.from_env(config_overrides)
    database = Database(config.db_path)
    database.initialize()
    operation_lock = OperationLock()
    ynab_client = YNABClient(config.ynab_access_token, transport=ynab_transport) if config.ynab_access_token else None
    ynab_sync = YNABSyncService(config=config, database=database, client=ynab_client)

    services = ServiceContainer(
        config=config,
        database=database,
        budget_importer=BudgetImporter(database),
        budget_workbook_source=create_budget_workbook_source(
            config,
            transport=budget_transport,
            access_token_provider=budget_access_token_provider,
        ),
        ynab_sync=ynab_sync,
        reconcile=ReconciliationService(database=database, ynab_sync=ynab_sync),
        reports=ReportService(config=config, database=database, operation_lock=operation_lock),
        analytics=AnalyticsService(config=config, database=database, operation_lock=operation_lock),
        review=None,
        scheduled_refresh=None,
        operation_lock=operation_lock,
        plan=PlanService(database=database),
    )
    services.plan_exporter = PlanExporter(plan_service=services.plan)
    services.export_storage = ExportStorage(base_dir=database.db_path.parent)
    services.sheets_publisher = create_sheets_publisher(
        plan_service=services.plan,
        config=config,
    )
    services.review = WeeklyReviewService(reports=services.reports, analytics=services.analytics)
    services.ai = AIService(config=config, container=services)
    services.scheduled_refresh = ScheduledRefreshService(
        enabled=config.scheduled_refresh_enabled,
        bootstrap_on_start=config.scheduled_refresh_bootstrap_on_start,
        interval_minutes=config.scheduled_refresh_interval_minutes,
        database=database,
        operation_lock=operation_lock,
        container=services,
    )
    services.reports.scheduled_refresh = services.scheduled_refresh
    services.scheduled_refresh.start()

    app = Flask(__name__)
    app.config["FINCLAIDE_CONFIG"] = config
    app.extensions["finclaide"] = services

    @app.get("/healthz")
    def healthcheck():
        return jsonify({"status": "ok"})

    app.register_blueprint(api)
    app.register_blueprint(analytics_api)
    app.register_blueprint(ui_api)
    register_error_handlers(app)
    register_frontend(app)
    return app
