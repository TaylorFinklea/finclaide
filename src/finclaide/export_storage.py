from __future__ import annotations

from pathlib import Path


class ExportStorage:
    """Persists rendered xlsx bytes keyed by run id under
    `{base_dir}/exports/{run_id}.xlsx`. Pruned on write to keep at most
    `keep` files (defaults to 20). Files don't survive container restarts
    in v1; if the operator wants a long-lived copy they download it
    immediately."""

    def __init__(self, base_dir: Path, *, keep: int = 20):
        self._base_dir = Path(base_dir) / "exports"
        self._keep = keep
        self._base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def path_for(self, run_id: int) -> Path:
        return self._base_dir / f"{run_id}.xlsx"

    def write(self, run_id: int, content: bytes) -> Path:
        path = self.path_for(run_id)
        path.write_bytes(content)
        self._prune()
        return path

    def _prune(self) -> None:
        files = sorted(
            self._base_dir.glob("*.xlsx"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for stale in files[self._keep :]:
            try:
                stale.unlink()
            except FileNotFoundError:
                pass
