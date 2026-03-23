from __future__ import annotations

import httpx
from flask import Flask, jsonify

from finclaide.analytics import AnalyticsService
from finclaide.analytics_api import analytics_api
from finclaide.api import api, register_error_handlers
from finclaide.budget_sheet import BudgetImporter
from finclaide.budget_source import create_budget_workbook_source
from finclaide.config import AppConfig
from finclaide.database import Database
from finclaide.frontend import register_frontend
from finclaide.locking import OperationLock
from finclaide.scheduled_refresh import ScheduledRefreshService
from finclaide.services import ReconciliationService, ReportService, ServiceContainer
from finclaide.ui_api import ui_api
from finclaide.ynab import YNABClient, YNABSyncService


def create_app(
    config_overrides: dict | None = None,
    *,
    ynab_transport: httpx.BaseTransport | None = None,
    budget_transport: httpx.BaseTransport | None = None,
) -> Flask:
    config = AppConfig.from_env(config_overrides)
    database = Database(config.db_path)
    database.initialize()
    operation_lock = OperationLock()
    ynab_client = YNABClient(config.ynab_access_token, transport=ynab_transport) if config.ynab_access_token else None

    services = ServiceContainer(
        config=config,
        database=database,
        budget_importer=BudgetImporter(database),
        budget_workbook_source=create_budget_workbook_source(config, transport=budget_transport),
        ynab_sync=YNABSyncService(config=config, database=database, client=ynab_client),
        reconcile=ReconciliationService(database=database),
        reports=ReportService(config=config, database=database, operation_lock=operation_lock),
        analytics=AnalyticsService(config=config, database=database, operation_lock=operation_lock),
        scheduled_refresh=None,
        operation_lock=operation_lock,
    )
    services.scheduled_refresh = ScheduledRefreshService(
        enabled=config.scheduled_refresh_enabled,
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
