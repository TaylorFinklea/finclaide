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

CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_year INTEGER NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'archived', 'draft', 'scenario')),
    source TEXT NOT NULL CHECK (source IN ('imported', 'edited')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT,
    source_import_id INTEGER,
    FOREIGN KEY (source_import_id) REFERENCES budget_imports(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS plan_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    group_name TEXT NOT NULL,
    category_name TEXT NOT NULL,
    block TEXT NOT NULL CHECK (block IN ('monthly','annual','one_time','stipends','savings')),
    planned_milliunits INTEGER NOT NULL DEFAULT 0,
    annual_target_milliunits INTEGER NOT NULL DEFAULT 0,
    due_month INTEGER CHECK (due_month IS NULL OR due_month BETWEEN 1 AND 12),
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (plan_id, group_name, category_name),
    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_plans_active_per_year
    ON plans(plan_year)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_plan_categories_plan_id
    ON plan_categories(plan_id);

CREATE TABLE IF NOT EXISTS plan_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN (
        'ui_create', 'ui_update', 'ui_delete', 'ui_rename',
        'importer', 'migration', 'restore'
    )),
    summary TEXT,
    change_count INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_plan_revisions_plan_created
    ON plan_revisions(plan_id, created_at DESC);

DROP VIEW IF EXISTS v_latest_planned_categories;

CREATE VIEW v_latest_planned_categories AS
SELECT
    pc.id,
    pc.plan_id AS import_id,
    pc.group_name,
    pc.category_name,
    pc.block,
    pc.planned_milliunits,
    pc.annual_target_milliunits,
    pc.due_month,
    NULL AS formula_text,
    NULL AS source_cell,
    NULL AS planned_group_id
FROM plan_categories pc
JOIN plans p ON p.id = pc.plan_id
WHERE p.status = 'active'
ORDER BY pc.id;

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
        # Run the plans.status CHECK widening BEFORE SCHEMA_SQL so the
        # `v_latest_planned_categories` view (which references plans) is
        # recreated against the migrated table on the executescript pass.
        # The migration is a no-op on fresh installs and on already-migrated
        # installs.
        self._migrate_plans_status_widen()
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
        self._hydrate_plan_from_latest_import_if_empty()

    def _migrate_plans_status_widen(self) -> None:
        """Widen plans.status CHECK to include 'draft' and 'scenario' on
        existing installs created before Phase 2.5b. Idempotent — fresh
        installs already get the new shape from SCHEMA_SQL, and re-runs
        against the new shape detect 'draft' in the stored DDL and exit."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        try:
            connection.row_factory = sqlite3.Row
            sql_row = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='plans'"
            ).fetchone()
            if sql_row is None:
                return
            if "'draft'" in sql_row["sql"] and "'scenario'" in sql_row["sql"]:
                return
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.executescript(
                """
                BEGIN;
                CREATE TABLE plans_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_year INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('active', 'archived', 'draft', 'scenario')),
                    source TEXT NOT NULL CHECK (source IN ('imported', 'edited')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    archived_at TEXT,
                    source_import_id INTEGER,
                    FOREIGN KEY (source_import_id) REFERENCES budget_imports(id) ON DELETE SET NULL
                );
                INSERT INTO plans_new (
                    id, plan_year, name, status, source,
                    created_at, updated_at, archived_at, source_import_id
                )
                SELECT id, plan_year, name, status, source,
                       created_at, updated_at, archived_at, source_import_id
                FROM plans;
                DROP TABLE plans;
                ALTER TABLE plans_new RENAME TO plans;
                CREATE UNIQUE INDEX IF NOT EXISTS idx_plans_active_per_year
                    ON plans(plan_year)
                    WHERE status = 'active';
                COMMIT;
                """
            )
            connection.execute("PRAGMA foreign_keys = ON")
        finally:
            connection.close()

    def _hydrate_plan_from_latest_import_if_empty(self) -> None:
        """If the new plans table is empty but the legacy budget_imports has
        data, create an active plan from the most recent import. Idempotent —
        no-op when any plans row already exists, and no-op when no legacy
        imports exist (fresh install)."""
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT COUNT(*) AS n FROM plans"
            ).fetchone()
            if int(existing["n"]) > 0:
                return
            latest = connection.execute(
                "SELECT * FROM v_latest_budget_import"
            ).fetchone()
            if latest is None:
                return
            now = utc_now()
            plan_cursor = connection.execute(
                """
                INSERT INTO plans(
                    plan_year, name, status, source,
                    created_at, updated_at, source_import_id
                )
                VALUES (?, ?, 'active', 'imported', ?, ?, ?)
                """,
                (
                    int(latest["plan_year"]),
                    latest["sheet_name"],
                    now,
                    now,
                    int(latest["id"]),
                ),
            )
            new_plan_id = int(plan_cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO plan_categories(
                    plan_id, group_name, category_name, block,
                    planned_milliunits, annual_target_milliunits, due_month,
                    notes, created_at, updated_at
                )
                SELECT
                    ?, group_name, category_name, block,
                    planned_milliunits, annual_target_milliunits, due_month,
                    NULL, ?, ?
                FROM planned_categories
                WHERE import_id = ?
                ORDER BY id
                """,
                (new_plan_id, now, now, int(latest["id"])),
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
