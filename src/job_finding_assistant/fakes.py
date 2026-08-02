"""In-memory fakes for Job Board / LLM / Master CV ports used in tests."""


class FakeJobBoardSession:
    def __init__(self, *, authenticated: bool = False) -> None:
        self._authenticated = authenticated

    def is_authenticated(self) -> bool:
        return self._authenticated


class FakeMasterCvStore:
    def __init__(self, path: str | None = None) -> None:
        self._path = path

    def master_cv_path(self) -> str | None:
        return self._path


class FakeLlmJudge:
    def available(self) -> bool:
        return False


class FakeLlmCvTailor:
    def available(self) -> bool:
        return False
