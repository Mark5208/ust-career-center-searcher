"""Assistant seam: Master CV path, Candidate Snapshot, freeform constraint file paths."""

from pathlib import Path

from job_finding_assistant.assistant import Assistant
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.constraint_files_store import DiskConstraintFilesStore
from job_finding_assistant.fakes import (
    FakeJobBoardSession,
    FakeLlmCvTailor,
    FakeLlmJudge,
)
from job_finding_assistant.master_cv_store import DiskMasterCvStore


def _assistant(
    tmp_path: Path,
    *,
    master_cv: DiskMasterCvStore | None = None,
    constraint_files: DiskConstraintFilesStore | None = None,
) -> Assistant:
    return Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=FakeJobBoardSession(),
        master_cv=master_cv or DiskMasterCvStore(tmp_path / "master_cv_state"),
        llm_judge=FakeLlmJudge(),
        llm_cv_tailor=FakeLlmCvTailor(),
        constraint_files=constraint_files
        or DiskConstraintFilesStore(tmp_path / "constraint_files_state"),
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


def test_assistant_keeps_skills_and_tools_sections_as_written(tmp_path: Path) -> None:
    master_cv_path = tmp_path / "master.tex"
    master_cv_path.write_text(
        r"""
\documentclass{article}
\begin{document}
\section{Skills}
Python, LaTeX

\section{Tools}
SQLite, Git
\end{document}
""",
        encoding="utf-8",
    )
    assistant = _assistant(tmp_path)

    assistant.set_master_cv_path(str(master_cv_path))
    snapshot = assistant.get_candidate_snapshot()

    assert snapshot is not None
    assert snapshot.skills_tools == ["Python, LaTeX", "SQLite, Git"]


def test_assistant_rebuilds_candidate_snapshot_when_master_cv_changes(
    tmp_path: Path,
) -> None:
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


def test_assistant_sets_constraint_file_paths_without_overwriting(tmp_path: Path) -> None:
    hc_path = tmp_path / "hard.txt"
    prefs_path = tmp_path / "prefs.txt"
    hc_body = "Hong Kong only\n"
    prefs_body = "Prefer fintech\n"
    hc_path.write_text(hc_body, encoding="utf-8")
    prefs_path.write_text(prefs_body, encoding="utf-8")
    assistant = _assistant(tmp_path)

    assistant.set_hard_constraints_path(str(hc_path))
    assistant.set_preferences_path(str(prefs_path))

    assert assistant.get_hard_constraints_path() == str(hc_path.resolve())
    assert assistant.get_preferences_path() == str(prefs_path.resolve())
    assert hc_path.read_text(encoding="utf-8") == hc_body
    assert prefs_path.read_text(encoding="utf-8") == prefs_body

    reloaded = _assistant(tmp_path)
    assert reloaded.get_hard_constraints_path() == str(hc_path.resolve())
    assert reloaded.get_preferences_path() == str(prefs_path.resolve())


def test_assistant_clears_constraint_file_paths(tmp_path: Path) -> None:
    hc_path = tmp_path / "hard.txt"
    hc_path.write_text("Remote only\n", encoding="utf-8")
    assistant = _assistant(tmp_path)
    assistant.set_hard_constraints_path(str(hc_path))
    assert assistant.get_hard_constraints_path() is not None

    assistant.clear_hard_constraints_path()
    assistant.clear_preferences_path()

    assert assistant.get_hard_constraints_path() is None
    assert assistant.get_preferences_path() is None
    assert hc_path.read_text(encoding="utf-8") == "Remote only\n"
