from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    details_json TEXT
);

CREATE TABLE IF NOT EXISTS ynab_sync_state (
    plan_id TEXT PRIMARY KEY,
    server_knowledge INTEGER,
    last_synced_at TEXT
);

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT,
    on_budget INTEGER NOT NULL DEFAULT 0,
    closed INTEGER NOT NULL DEFAULT 0,
    balance_milliunits INTEGER NOT NULL DEFAULT 0,
    raw_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS category_groups (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    name TEXT NOT NULL,
    hidden INTEGER NOT NULL DEFAULT 0,
    deleted INTEGER NOT NULL DEFAULT 0,
    raw_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    group_name TEXT NOT NULL,
    name TEXT NOT NULL,
    hidden INTEGER NOT NULL DEFAULT 0,
    deleted INTEGER NOT NULL DEFAULT 0,
    balance_milliunits INTEGER NOT NULL DEFAULT 0,
    raw_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(group_id) REFERENCES category_groups(id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    account_id TEXT,
    date TEXT NOT NULL,
    payee_name TEXT,
    memo TEXT,
    cleared TEXT,
    approved INTEGER NOT NULL DEFAULT 0,
    category_id TEXT,
    category_name TEXT,
    group_name TEXT,
    amount_milliunits INTEGER NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0,
    raw_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS budget_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workbook_path TEXT NOT NULL,
    workbook_sha256 TEXT NOT NULL,
    sheet_name TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    plan_year INTEGER NOT NULL,
    summary_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS planned_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    block TEXT NOT NULL,
    UNIQUE(import_id, name),
    FOREIGN KEY(import_id) REFERENCES budget_imports(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS planned_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER NOT NULL,
    planned_group_id INTEGER NOT NULL,
    group_name TEXT NOT NULL,
    category_name TEXT NOT NULL,
    block TEXT NOT NULL,
    source_cell TEXT NOT NULL,
    planned_milliunits INTEGER NOT NULL,
    annual_target_milliunits INTEGER NOT NULL DEFAULT 0,
    due_month INTEGER,
    formula_text TEXT,
    UNIQUE(import_id, group_name, category_name),
    FOREIGN KEY(import_id) REFERENCES budget_imports(id) ON DELETE CASCADE,
    FOREIGN KEY(planned_group_id) REFERENCES planned_groups(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reconciliation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    status TEXT NOT NULL,
    mismatch_count INTEGER NOT NULL,
    summary_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reconciliation_mismatches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reconciliation_id INTEGER NOT NULL,
    group_name TEXT NOT NULL,
    category_name TEXT NOT NULL,
    reason TEXT NOT NULL,
    FOREIGN KEY(reconciliation_id) REFERENCES reconciliation_results(id) ON DELETE CASCADE
);

CREATE VIEW IF NOT EXISTS v_latest_budget_import AS
SELECT *
FROM budget_imports
WHERE id = (SELECT id FROM budget_imports ORDER BY imported_at DESC, id DESC LIMIT 1);

CREATE VIEW IF NOT EXISTS v_latest_planned_categories AS
SELECT pc.*
FROM planned_categories pc
JOIN v_latest_budget_import bi ON pc.import_id = bi.id;

CREATE VIEW IF NOT EXISTS v_latest_reconciliation AS
SELECT *
FROM reconciliation_results
WHERE id = (SELECT id FROM reconciliation_results ORDER BY run_at DESC, id DESC LIMIT 1);

CREATE VIEW IF NOT EXISTS v_recent_transactions AS
SELECT *
FROM transactions
WHERE deleted = 0
ORDER BY date DESC, id DESC;
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
            connection.execute(
                """
                INSERT INTO metadata(key, value)
                VALUES ('schema_initialized_at', ?)
                ON CONFLICT(key) DO NOTHING
                """,
                (utc_now(),),
            )

    def record_run(
        self,
        source: str,
        status: str,
        details: dict[str, Any] | None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sync_runs(source, status, started_at, finished_at, details_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    source,
                    status,
                    started_at or utc_now(),
                    finished_at or utc_now(),
                    json.dumps(details or {}, sort_keys=True),
                ),
            )
