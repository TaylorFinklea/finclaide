from __future__ import annotations

import atexit
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Event, Lock, Thread
from typing import Any

from finclaide.database import Database, utc_now
from finclaide.errors import DataIntegrityError, OperationInProgressError
from finclaide.operations import run_budget_import, run_reconcile, run_ynab_sync


def _iso_after_minutes(minutes: int) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


@dataclass
class ScheduledRefreshService:
    enabled: bool
    interval_minutes: int
    database: Database
    operation_lock: Any
    container: Any
    _state_lock: Lock = field(default_factory=Lock)
    _stop_event: Event = field(default_factory=Event)
    _thread: Thread | None = None
    _next_run_at: str | None = None
    _last_started_at: str | None = None
    _last_finished_at: str | None = None
    _last_status: str | None = None
    _last_error: str | None = None

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._set_next_run()
        self._thread = Thread(target=self._loop, name="finclaide-scheduled-refresh", daemon=True)
        self._thread.start()
        atexit.register(self.stop)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None

    def snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            return {
                "enabled": self.enabled,
                "interval_minutes": self.interval_minutes,
                "next_run_at": self._next_run_at,
                "last_started_at": self._last_started_at,
                "last_finished_at": self._last_finished_at,
                "last_status": self._last_status,
                "last_error": self._last_error,
            }

    def run_once(self) -> dict[str, Any]:
        started_at = utc_now()
        with self._state_lock:
            self._last_started_at = started_at
            self._last_error = None

        details: dict[str, Any]
        status: str
        try:
            with self.operation_lock.guard("scheduled_refresh"):
                budget_import = run_budget_import(self.container)
                ynab_sync = run_ynab_sync(self.container)
                try:
                    reconcile = run_reconcile(self.container)
                    status = "success"
                    details = {
                        "budget_import": budget_import,
                        "ynab_sync": ynab_sync,
                        "reconcile": reconcile,
                    }
                except DataIntegrityError as error:
                    status = "failed"
                    details = {
                        "budget_import": budget_import,
                        "ynab_sync": ynab_sync,
                        "reconcile_error": str(error),
                    }
        except OperationInProgressError as error:
            status = "skipped"
            details = {"error": str(error)}
        except Exception as error:
            status = "failed"
            details = {"error": str(error)}

        finished_at = utc_now()
        with self._state_lock:
            self._last_finished_at = finished_at
            self._last_status = status
            self._last_error = details.get("error") or details.get("reconcile_error")
            self._set_next_run()

        self.database.record_run(
            source="scheduled_refresh",
            status=status,
            details=details,
            started_at=started_at,
            finished_at=finished_at,
        )
        return {"status": status, **details}

    def _loop(self) -> None:
        while not self._stop_event.wait(self.interval_minutes * 60):
            self.run_once()

    def _set_next_run(self) -> None:
        self._next_run_at = _iso_after_minutes(self.interval_minutes) if self.enabled else None
