from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from finclaide.config import AppConfig
from finclaide.database import Database, utc_now
from finclaide.errors import ConfigError


def _truthy(value: Any) -> int:
    return 1 if value else 0


class YNABClient:
    base_url = "https://api.ynab.com/v1"

    def __init__(
        self,
        access_token: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        payload = self._request_json("GET", f"/plans/{plan_id}")
        return payload["data"]["plan"]

    def get_accounts(self, plan_id: str) -> list[dict[str, Any]]:
        payload = self._request_json("GET", f"/plans/{plan_id}/accounts")
        return payload["data"]["accounts"]

    def get_categories(self, plan_id: str) -> list[dict[str, Any]]:
        payload = self._request_json("GET", f"/plans/{plan_id}/categories")
        return payload["data"]["category_groups"]

    def get_transactions(
        self,
        plan_id: str,
        last_knowledge_of_server: int | None = None,
    ) -> dict[str, Any]:
        params = {}
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = str(last_knowledge_of_server)
        payload = self._request_json("GET", f"/plans/{plan_id}/transactions", params=params)
        return payload["data"]

    def _request_json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()


@dataclass
class YNABSyncService:
    config: AppConfig
    database: Database
    client: YNABClient | None

    def sync(self) -> dict[str, Any]:
        started_at = utc_now()
        plan_id = self.config.ynab_plan_id
        try:
            if not plan_id:
                raise ConfigError("YNAB_PLAN_ID must be configured before sync.")
            if not self.client:
                raise ConfigError("YNAB_ACCESS_TOKEN must be configured before sync.")

            with self.database.connect() as connection:
                row = connection.execute(
                    "SELECT server_knowledge FROM ynab_sync_state WHERE plan_id = ?",
                    (plan_id,),
                ).fetchone()
                last_knowledge = int(row["server_knowledge"]) if row and row["server_knowledge"] is not None else None

            plan = self.client.get_plan(plan_id)
            accounts = self.client.get_accounts(plan_id)
            category_groups = self.client.get_categories(plan_id)
            transactions_payload = self.client.get_transactions(plan_id, last_knowledge_of_server=last_knowledge)
            transactions = transactions_payload["transactions"]
            server_knowledge = transactions_payload.get("server_knowledge")
            synced_at = utc_now()

            with self.database.connect() as connection:
                for account in accounts:
                    connection.execute(
                        """
                        INSERT INTO accounts(id, plan_id, name, type, on_budget, closed, balance_milliunits, raw_json, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            plan_id = excluded.plan_id,
                            name = excluded.name,
                            type = excluded.type,
                            on_budget = excluded.on_budget,
                            closed = excluded.closed,
                            balance_milliunits = excluded.balance_milliunits,
                            raw_json = excluded.raw_json,
                            updated_at = excluded.updated_at
                        """,
                        (
                            account["id"],
                            plan_id,
                            account["name"],
                            account.get("type"),
                            _truthy(account.get("on_budget")),
                            _truthy(account.get("closed")),
                            int(account.get("balance", 0)),
                            json.dumps(account, sort_keys=True),
                            synced_at,
                        ),
                    )

                for group in category_groups:
                    connection.execute(
                        """
                        INSERT INTO category_groups(id, plan_id, name, hidden, deleted, raw_json, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            plan_id = excluded.plan_id,
                            name = excluded.name,
                            hidden = excluded.hidden,
                            deleted = excluded.deleted,
                            raw_json = excluded.raw_json,
                            updated_at = excluded.updated_at
                        """,
                        (
                            group["id"],
                            plan_id,
                            group["name"],
                            _truthy(group.get("hidden")),
                            _truthy(group.get("deleted")),
                            json.dumps(group, sort_keys=True),
                            synced_at,
                        ),
                    )
                    for category in group.get("categories", []):
                        connection.execute(
                            """
                            INSERT INTO categories(id, plan_id, group_id, group_name, name, hidden, deleted, balance_milliunits, raw_json, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(id) DO UPDATE SET
                                plan_id = excluded.plan_id,
                                group_id = excluded.group_id,
                                group_name = excluded.group_name,
                                name = excluded.name,
                                hidden = excluded.hidden,
                                deleted = excluded.deleted,
                                balance_milliunits = excluded.balance_milliunits,
                                raw_json = excluded.raw_json,
                                updated_at = excluded.updated_at
                            """,
                            (
                                category["id"],
                                plan_id,
                                group["id"],
                                group["name"],
                                category["name"],
                                _truthy(category.get("hidden")),
                                _truthy(category.get("deleted")),
                                int(category.get("balance", 0)),
                                json.dumps(category, sort_keys=True),
                                synced_at,
                            ),
                        )

                for transaction in transactions:
                    connection.execute(
                        """
                        INSERT INTO transactions(
                            id,
                            plan_id,
                            account_id,
                            date,
                            payee_name,
                            memo,
                            cleared,
                            approved,
                            category_id,
                            category_name,
                            group_name,
                            amount_milliunits,
                            deleted,
                            raw_json,
                            updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            plan_id = excluded.plan_id,
                            account_id = excluded.account_id,
                            date = excluded.date,
                            payee_name = excluded.payee_name,
                            memo = excluded.memo,
                            cleared = excluded.cleared,
                            approved = excluded.approved,
                            category_id = excluded.category_id,
                            category_name = excluded.category_name,
                            group_name = excluded.group_name,
                            amount_milliunits = excluded.amount_milliunits,
                            deleted = excluded.deleted,
                            raw_json = excluded.raw_json,
                            updated_at = excluded.updated_at
                        """,
                        (
                            transaction["id"],
                            plan_id,
                            transaction.get("account_id"),
                            transaction["date"],
                            transaction.get("payee_name"),
                            transaction.get("memo"),
                            transaction.get("cleared"),
                            _truthy(transaction.get("approved")),
                            transaction.get("category_id"),
                            transaction.get("category_name"),
                            transaction.get("category_group_name"),
                            int(transaction.get("amount", 0)),
                            _truthy(transaction.get("deleted")),
                            json.dumps(transaction, sort_keys=True),
                            synced_at,
                        ),
                    )

                connection.execute(
                    """
                    INSERT INTO ynab_sync_state(plan_id, server_knowledge, last_synced_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(plan_id) DO UPDATE SET
                        server_knowledge = excluded.server_knowledge,
                        last_synced_at = excluded.last_synced_at
                    """,
                    (plan_id, server_knowledge, synced_at),
                )

            summary = {
                "plan_id": plan_id,
                "plan_name": plan.get("name"),
                "account_count": len(accounts),
                "group_count": len(category_groups),
                "transaction_count": len(transactions),
                "server_knowledge": server_knowledge,
                "synced_at": synced_at,
            }
            self.database.record_run(
                source="ynab_sync",
                status="success",
                details=summary,
                started_at=started_at,
                finished_at=synced_at,
            )
            return summary
        except Exception as error:
            self.database.record_run(
                source="ynab_sync",
                status="failed",
                details={"plan_id": plan_id, "error": str(error)},
                started_at=started_at,
                finished_at=utc_now(),
            )
            raise
