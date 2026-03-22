from __future__ import annotations

from pathlib import Path

import pytest
import httpx

from finclaide.app import create_app
from finclaide.database import Database
from tests.support import make_transport
from tests.workbook_builder import build_budget_workbook


@pytest.fixture
def budget_workbook(tmp_path: Path) -> Path:
    return build_budget_workbook(tmp_path / "Budget.xlsx")


@pytest.fixture
def app_factory(tmp_path: Path):
    def factory(
        *,
        workbook_path: Path | None = None,
        workbook_url: str | None = None,
        categories_fixture: str = "categories.json",
        transactions_fixture: str = "transactions_initial.json",
        budget_transport: httpx.BaseTransport | None = None,
    ):
        db_path = tmp_path / "finclaide.db"
        app = create_app(
            {
                "api_token": "test-token",
                "ynab_access_token": "token",
                "ynab_plan_id": "plan-123",
                "db_path": db_path,
                "budget_xlsx": workbook_path or build_budget_workbook(tmp_path / "Budget.xlsx"),
                "budget_xlsx_url": workbook_url,
                "host": "127.0.0.1",
                "port": 8050,
            },
            ynab_transport=make_transport(
                categories_fixture=categories_fixture,
                transactions_fixture=transactions_fixture,
            ),
            budget_transport=budget_transport,
        )
        app.testing = True
        return app

    return factory


@pytest.fixture
def client(app_factory):
    app = app_factory()
    return app.test_client()


@pytest.fixture
def auth_header() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def ui_headers() -> dict[str, str]:
    return {"X-Finclaide-UI": "1"}


@pytest.fixture
def database_path(app_factory) -> Path:
    app = app_factory()
    return Path(app.config["FINCLAIDE_CONFIG"].db_path)


@pytest.fixture
def database(database_path: Path) -> Database:
    return Database(database_path)
