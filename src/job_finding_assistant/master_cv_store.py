"""Disk-backed Master CV path and Candidate Snapshot rebuild (read-only on the YAML file)."""

from __future__ import annotations

from pathlib import Path

from job_finding_assistant.candidate_snapshot import (
    CandidateSnapshot,
    InvalidMasterCvError,
    build_candidate_snapshot,
)


class DiskMasterCvStore:
    """Stores the configured Master CV path; never writes to the Master CV file."""

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._path_file = self._state_dir / "master_cv_path.txt"
        self._path: str | None = self._load_path()
        self._snapshot: CandidateSnapshot | None = None
        self._snapshot_mtime_ns: int | None = None
        if self._path is not None:
            self._rebuild_snapshot()

    def _load_path(self) -> str | None:
        if not self._path_file.is_file():
            return None
        text = self._path_file.read_text(encoding="utf-8").strip()
        return text or None

    def master_cv_path(self) -> str | None:
        return self._path

    def set_master_cv_path(self, path: str) -> None:
        resolved = str(Path(path).expanduser().resolve())
        self._path = resolved
        self._path_file.write_text(resolved + "\n", encoding="utf-8")
        self._rebuild_snapshot()

    def candidate_snapshot(self) -> CandidateSnapshot | None:
        self._rebuild_if_master_cv_changed()
        return self._snapshot

    def _clear_snapshot(self) -> None:
        self._snapshot = None
        self._snapshot_mtime_ns = None

    def _rebuild_if_master_cv_changed(self) -> None:
        if self._path is None:
            return
        yaml_path = Path(self._path)
        if not yaml_path.is_file():
            self._clear_snapshot()
            return
        mtime_ns = yaml_path.stat().st_mtime_ns
        if self._snapshot_mtime_ns != mtime_ns:
            self._rebuild_snapshot()

    def _rebuild_snapshot(self) -> None:
        if self._path is None:
            self._clear_snapshot()
            return
        yaml_path = Path(self._path)
        if not yaml_path.is_file():
            self._clear_snapshot()
            return
        try:
            text = yaml_path.read_text(encoding="utf-8")
            self._snapshot = build_candidate_snapshot(text)
            self._snapshot_mtime_ns = yaml_path.stat().st_mtime_ns
        except (OSError, UnicodeError, InvalidMasterCvError):
            self._clear_snapshot()
