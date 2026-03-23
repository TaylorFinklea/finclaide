from __future__ import annotations

from pathlib import Path

from finclaide.config import AppConfig
from finclaide.database import Database
from finclaide.ynab import YNABClient, YNABSyncService
from tests.support import make_transport


def test_ynab_sync_initial_and_delta(tmp_path: Path):
    database = Database(tmp_path / "test.db")
    database.initialize()
    config = AppConfig(
        ynab_access_token="token",
        ynab_plan_id="plan-123",
        api_token="api-token",
        db_path=tmp_path / "test.db",
        budget_xlsx=tmp_path / "Budget.xlsx",
        budget_xlsx_url=None,
        budget_xlsx_download_path=None,
        scheduled_refresh_enabled=False,
        scheduled_refresh_interval_minutes=360,
        host="127.0.0.1",
        port=8050,
    )
    service = YNABSyncService(
        config=config,
        database=database,
        client=YNABClient("token", transport=make_transport()),
    )

    first_summary = service.sync()

    assert first_summary["server_knowledge"] == 100
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) AS count FROM accounts").fetchone()["count"] == 2
        assert connection.execute("SELECT COUNT(*) AS count FROM categories").fetchone()["count"] == 13
        assert connection.execute("SELECT deleted FROM transactions WHERE id = 'txn-fuel'").fetchone()["deleted"] == 0

    delta_service = YNABSyncService(
        config=config,
        database=database,
        client=YNABClient(
            "token",
            transport=make_transport(transactions_fixture="transactions_delta.json"),
        ),
    )
    second_summary = delta_service.sync()

    assert second_summary["server_knowledge"] == 101
    with database.connect() as connection:
        fuel_row = connection.execute(
            "SELECT deleted FROM transactions WHERE id = 'txn-fuel'"
        ).fetchone()
        vacation_row = connection.execute(
            "SELECT COUNT(*) AS count FROM transactions WHERE id = 'txn-vacation'"
        ).fetchone()
        assert fuel_row["deleted"] == 1
        assert vacation_row["count"] == 1
