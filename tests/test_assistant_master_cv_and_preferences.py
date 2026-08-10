"""Assistant seam: Master CV YAML path, Candidate Snapshot, freeform constraint file paths."""

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

_SAMPLE_MASTER_CV = """\
cv:
  name: Alice Example
  email: alice@example.com
  sections:
    education:
      - institution: HKUST
        area: Computer Science
        degree: BEng
        end_date: "2024"
    experience:
      - company: Acme Corp
        position: Software Intern
        highlights:
          - Built internal tools
    projects:
      - name: Campus Event Finder
        summary: Campus event discovery app
    skills:
      - label: Languages
        details: Python, YAML, SQLite
"""


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


def test_assistant_get_candidate_files_returns_paths_snapshot_and_errors(
    tmp_path: Path,
) -> None:
    master_cv_path = tmp_path / "master_CV.yaml"
    master_cv_path.write_text(_SAMPLE_MASTER_CV, encoding="utf-8")
    hc_path = tmp_path / "hard.txt"
    prefs_path = tmp_path / "prefs.txt"
    hc_path.write_text("Hong Kong only\n", encoding="utf-8")
    prefs_path.write_text("Prefer fintech\n", encoding="utf-8")
    assistant = _assistant(tmp_path)

    assistant.set_master_cv_path(str(master_cv_path))
    assistant.set_hard_constraints_path(str(hc_path))
    assistant.set_preferences_path(str(prefs_path))

    view = assistant.get_candidate_files()

    assert view.master_cv_path == str(master_cv_path.resolve())
    assert view.hard_constraints_path == str(hc_path.resolve())
    assert view.preferences_path == str(prefs_path.resolve())
    assert view.snapshot is not None
    assert view.snapshot.contact == "Alice Example, alice@example.com"
    assert view.errors == []


def test_assistant_does_not_expose_legacy_candidate_file_getters() -> None:
    for name in (
        "get_master_cv_path",
        "get_hard_constraints_path",
        "get_preferences_path",
        "get_candidate_snapshot",
        "get_candidate_file_errors",
    ):
        assert not hasattr(Assistant, name)


def test_assistant_sets_master_cv_path_without_overwriting_file(tmp_path: Path) -> None:
    master_cv_path = tmp_path / "master_CV.yaml"
    original = "cv:\n  name: Original Master CV\n"
    master_cv_path.write_text(original, encoding="utf-8")
    assistant = _assistant(tmp_path)

    assistant.set_master_cv_path(str(master_cv_path))

    assert assistant.get_candidate_files().master_cv_path == str(master_cv_path.resolve())
    assert master_cv_path.read_text(encoding="utf-8") == original


def test_assistant_builds_candidate_snapshot_from_master_cv(tmp_path: Path) -> None:
    master_cv_path = tmp_path / "master_CV.yaml"
    master_cv_path.write_text(_SAMPLE_MASTER_CV, encoding="utf-8")
    assistant = _assistant(tmp_path)

    assistant.set_master_cv_path(str(master_cv_path))
    snapshot = assistant.get_candidate_files().snapshot

    assert snapshot is not None
    assert snapshot.contact == "Alice Example, alice@example.com"
    assert snapshot.education == ["BEng, Computer Science, HKUST, 2024"]
    assert snapshot.experience == [
        "Software Intern at Acme Corp\n- Built internal tools"
    ]
    assert snapshot.projects == ["Campus Event Finder: Campus event discovery app"]
    assert snapshot.skills_tools == ["Languages: Python, YAML, SQLite"]


def test_assistant_keeps_skills_and_tools_sections_as_written(tmp_path: Path) -> None:
    master_cv_path = tmp_path / "master_CV.yaml"
    master_cv_path.write_text(
        """\
cv:
  name: Alice Example
  sections:
    skills:
      - label: Languages
        details: Python, YAML
    tools:
      - label: Stack
        details: SQLite, Git
""",
        encoding="utf-8",
    )
    assistant = _assistant(tmp_path)

    assistant.set_master_cv_path(str(master_cv_path))
    snapshot = assistant.get_candidate_files().snapshot

    assert snapshot is not None
    assert snapshot.skills_tools == ["Languages: Python, YAML", "Stack: SQLite, Git"]


def test_assistant_rebuilds_candidate_snapshot_when_master_cv_changes(
    tmp_path: Path,
) -> None:
    master_cv_path = tmp_path / "master_CV.yaml"
    master_cv_path.write_text(_SAMPLE_MASTER_CV, encoding="utf-8")
    assistant = _assistant(tmp_path)
    assistant.set_master_cv_path(str(master_cv_path))
    assert assistant.get_candidate_files().snapshot is not None
    assert assistant.get_candidate_files().snapshot.skills_tools == [
        "Languages: Python, YAML, SQLite"
    ]

    updated = _SAMPLE_MASTER_CV.replace("Python, YAML, SQLite", "Rust, Go")
    master_cv_path.write_text(updated, encoding="utf-8")

    snapshot = assistant.get_candidate_files().snapshot

    assert snapshot is not None
    assert snapshot.skills_tools == ["Languages: Rust, Go"]
    assert master_cv_path.read_text(encoding="utf-8") == updated


def test_invalid_master_cv_yaml_yields_no_snapshot(tmp_path: Path) -> None:
    master_cv_path = tmp_path / "broken_CV.yaml"
    master_cv_path.write_text("cv: [\n  not: valid\n", encoding="utf-8")
    assistant = _assistant(tmp_path)

    assistant.set_master_cv_path(str(master_cv_path))

    assert assistant.get_candidate_files().snapshot is None
    assert master_cv_path.read_text(encoding="utf-8").startswith("cv: [")


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

    files = assistant.get_candidate_files()
    assert files.hard_constraints_path == str(hc_path.resolve())
    assert files.preferences_path == str(prefs_path.resolve())
    assert hc_path.read_text(encoding="utf-8") == hc_body
    assert prefs_path.read_text(encoding="utf-8") == prefs_body

    reloaded = _assistant(tmp_path).get_candidate_files()
    assert reloaded.hard_constraints_path == str(hc_path.resolve())
    assert reloaded.preferences_path == str(prefs_path.resolve())


def test_assistant_clears_constraint_file_paths(tmp_path: Path) -> None:
    hc_path = tmp_path / "hard.txt"
    hc_path.write_text("Remote only\n", encoding="utf-8")
    assistant = _assistant(tmp_path)
    assistant.set_hard_constraints_path(str(hc_path))
    assert assistant.get_candidate_files().hard_constraints_path is not None

    assistant.clear_hard_constraints_path()
    assistant.clear_preferences_path()

    files = assistant.get_candidate_files()
    assert files.hard_constraints_path is None
    assert files.preferences_path is None
    assert hc_path.read_text(encoding="utf-8") == "Remote only\n"
