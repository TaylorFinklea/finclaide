from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppConfig:
    ynab_access_token: str | None
    ynab_plan_id: str | None
    api_token: str | None
    db_path: Path
    budget_xlsx: Path
    host: str
    port: int
    frontend_dist: Path | None = None
    budget_sheet_name: str = "2026 Budget"

    @classmethod
    def from_env(cls, overrides: dict[str, Any] | None = None) -> "AppConfig":
        config = cls(
            ynab_access_token=os.getenv("YNAB_ACCESS_TOKEN"),
            ynab_plan_id=os.getenv("YNAB_PLAN_ID"),
            api_token=os.getenv("FINCLAIDE_API_TOKEN"),
            db_path=Path(os.getenv("FINCLAIDE_DB_PATH", "/data/finclaide.db")),
            budget_xlsx=Path(os.getenv("FINCLAIDE_BUDGET_XLSX", "/input/Budget.xlsx")),
            frontend_dist=(
                Path(frontend_dist)
                if (frontend_dist := os.getenv("FINCLAIDE_FRONTEND_DIST"))
                else None
            ),
            host=os.getenv("FINCLAIDE_HOST", "0.0.0.0"),
            port=int(os.getenv("FINCLAIDE_PORT", "8050")),
        )
        if not overrides:
            return config
        return replace(config, **overrides)
