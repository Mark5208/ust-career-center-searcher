"""Assistant seam: Master CV path, Candidate Snapshot rebuild, Preferences."""

from pathlib import Path

from job_finding_assistant.assistant import (
    Assistant,
    GapTolerance,
    LanguagePreference,
    Preferences,
)
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.fakes import (
    FakeJobBoardSession,
    FakeLlmCvTailor,
    FakeLlmJudge,
)
from job_finding_assistant.master_cv_store import DiskMasterCvStore


def _assistant(tmp_path: Path, *, master_cv: DiskMasterCvStore | None = None) -> Assistant:
    return Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=FakeJobBoardSession(),
        master_cv=master_cv or DiskMasterCvStore(tmp_path / "master_cv_state"),
        llm_judge=FakeLlmJudge(),
        llm_cv_tailor=FakeLlmCvTailor(),
    )


def test_assistant_sets_master_cv_path_without_overwriting_file(tmp_path: Path) -> None:
    master_cv_path = tmp_path / "master.tex"
    original = (
        r"\documentclass{article}"
        r"\begin{document}Original Master CV\end{document}"
    )
    master_cv_path.write_text(original, encoding="utf-8")
    assistant = _assistant(tmp_path)

    assistant.set_master_cv_path(str(master_cv_path))

    assert assistant.get_master_cv_path() == str(master_cv_path.resolve())
    assert master_cv_path.read_text(encoding="utf-8") == original


_SAMPLE_MASTER_CV = r"""
\documentclass{article}
\begin{document}
\section{Contact}
Alice Example, alice@example.com

\section{Education}
BEng Computer Science, HKUST, 2024

\section{Experience}
Software Intern at Acme Corp

\section{Projects}
Campus Event Finder

\section{Skills}
Python, LaTeX, SQLite
\end{document}
"""


def test_assistant_builds_candidate_snapshot_from_master_cv(tmp_path: Path) -> None:
    master_cv_path = tmp_path / "master.tex"
    master_cv_path.write_text(_SAMPLE_MASTER_CV, encoding="utf-8")
    assistant = _assistant(tmp_path)

    assistant.set_master_cv_path(str(master_cv_path))
    snapshot = assistant.get_candidate_snapshot()

    assert snapshot is not None
    assert snapshot.contact == "Alice Example, alice@example.com"
    assert snapshot.education == ["BEng Computer Science, HKUST, 2024"]
    assert snapshot.experience == ["Software Intern at Acme Corp"]
    assert snapshot.projects == ["Campus Event Finder"]
    assert snapshot.skills_tools == ["Python, LaTeX, SQLite"]


def test_assistant_rebuilds_candidate_snapshot_when_master_cv_changes(tmp_path: Path) -> None:
    master_cv_path = tmp_path / "master.tex"
    master_cv_path.write_text(_SAMPLE_MASTER_CV, encoding="utf-8")
    assistant = _assistant(tmp_path)
    assistant.set_master_cv_path(str(master_cv_path))
    assert assistant.get_candidate_snapshot() is not None
    assert assistant.get_candidate_snapshot().skills_tools == ["Python, LaTeX, SQLite"]

    updated = _SAMPLE_MASTER_CV.replace("Python, LaTeX, SQLite", "Rust, Go")
    master_cv_path.write_text(updated, encoding="utf-8")

    snapshot = assistant.get_candidate_snapshot()

    assert snapshot is not None
    assert snapshot.skills_tools == ["Rust, Go"]
    assert master_cv_path.read_text(encoding="utf-8") == updated


def test_assistant_persists_preferences_without_crawl_filters(tmp_path: Path) -> None:
    assistant = _assistant(tmp_path)

    empty = assistant.get_preferences()
    assert empty.languages == []
    assert empty.locations == []
    assert empty.gap_tolerance is None

    preferences = Preferences(
        languages=[
            LanguagePreference(language="English", level="Fluent"),
            LanguagePreference(language="Cantonese", level=None),
        ],
        locations=["Hong Kong", "Remote"],
        gap_tolerance=GapTolerance.SEMESTER,
    )
    assistant.update_preferences(preferences)

    reloaded = _assistant(tmp_path).get_preferences()
    assert reloaded == preferences
    assert not hasattr(reloaded, "crawl_filters")


def test_assistant_accepts_each_gap_tolerance_value_including_unset(tmp_path: Path) -> None:
    assistant = _assistant(tmp_path)

    for value in (
        GapTolerance.NONE,
        GapTolerance.SEMESTER,
        GapTolerance.YEAR,
        GapTolerance.ANY,
        None,
    ):
        assistant.update_preferences(
            Preferences(languages=[], locations=[], gap_tolerance=value)
        )
        assert assistant.get_preferences().gap_tolerance is value
