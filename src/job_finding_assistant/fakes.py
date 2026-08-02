"""In-memory fakes for Job Board / LLM / Master CV ports used in tests."""

from pathlib import Path

from job_finding_assistant.candidate_snapshot import CandidateSnapshot, build_candidate_snapshot


class FakeJobBoardSession:
    def __init__(self, *, authenticated: bool = False) -> None:
        self._authenticated = authenticated

    def is_authenticated(self) -> bool:
        return self._authenticated


class FakeMasterCvStore:
    def __init__(
        self,
        path: str | None = None,
        snapshot: CandidateSnapshot | None = None,
    ) -> None:
        self._path = path
        self._snapshot = snapshot

    def master_cv_path(self) -> str | None:
        return self._path

    def set_master_cv_path(self, path: str) -> None:
        self._path = path
        self._rebuild_from_path()

    def candidate_snapshot(self) -> CandidateSnapshot | None:
        if self._path is not None and Path(self._path).is_file():
            self._rebuild_from_path()
        return self._snapshot

    def _rebuild_from_path(self) -> None:
        if self._path is None:
            self._snapshot = None
            return
        latex_path = Path(self._path)
        if not latex_path.is_file():
            self._snapshot = None
            return
        self._snapshot = build_candidate_snapshot(latex_path.read_text(encoding="utf-8"))


class FakeLlmJudge:
    def available(self) -> bool:
        return False


class FakeLlmCvTailor:
    def available(self) -> bool:
        return False
