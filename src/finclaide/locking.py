from __future__ import annotations

from contextlib import contextmanager
from threading import Lock

from finclaide.errors import OperationInProgressError


class OperationLock:
    def __init__(self) -> None:
        self._lock = Lock()
        self.current_operation: str | None = None

    @contextmanager
    def guard(self, operation_name: str):
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            raise OperationInProgressError(
                f"Operation '{self.current_operation or 'unknown'}' is already running."
            )
        self.current_operation = operation_name
        try:
            yield
        finally:
            self.current_operation = None
            self._lock.release()
