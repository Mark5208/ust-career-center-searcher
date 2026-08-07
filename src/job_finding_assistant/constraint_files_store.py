"""Disk-backed Hard Constraints and Preferences file paths (read-only on those files)."""

from __future__ import annotations

from pathlib import Path

from job_finding_assistant.constraint_files import ConstraintFileRead, read_constraint_file


class DiskConstraintFilesStore:
    """Stores Hard Constraints / Preferences paths; never writes those user files."""

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._hc_path_file = self._state_dir / "hard_constraints_path.txt"
        self._prefs_path_file = self._state_dir / "preferences_path.txt"
        self._hard_constraints_path = self._load_path(self._hc_path_file)
        self._preferences_path = self._load_path(self._prefs_path_file)

    @staticmethod
    def _load_path(path_file: Path) -> str | None:
        if not path_file.is_file():
            return None
        text = path_file.read_text(encoding="utf-8").strip()
        return text or None

    def hard_constraints_path(self) -> str | None:
        return self._hard_constraints_path

    def preferences_path(self) -> str | None:
        return self._preferences_path

    def set_hard_constraints_path(self, path: str) -> None:
        resolved = str(Path(path).expanduser().resolve())
        self._hard_constraints_path = resolved
        self._hc_path_file.write_text(resolved + "\n", encoding="utf-8")

    def clear_hard_constraints_path(self) -> None:
        self._hard_constraints_path = None
        if self._hc_path_file.is_file():
            self._hc_path_file.unlink()

    def set_preferences_path(self, path: str) -> None:
        resolved = str(Path(path).expanduser().resolve())
        self._preferences_path = resolved
        self._prefs_path_file.write_text(resolved + "\n", encoding="utf-8")

    def clear_preferences_path(self) -> None:
        self._preferences_path = None
        if self._prefs_path_file.is_file():
            self._prefs_path_file.unlink()

    def read_hard_constraints(self) -> ConstraintFileRead:
        return read_constraint_file(self._hard_constraints_path)

    def read_preferences(self) -> ConstraintFileRead:
        return read_constraint_file(self._preferences_path)
