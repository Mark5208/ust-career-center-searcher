"""Assistant seam: Master CV Enrichment (ADR-0017)."""

from pathlib import Path

import pytest
import yaml

from job_finding_assistant.assistant import Assistant
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.constraint_files_store import DiskConstraintFilesStore
from job_finding_assistant.enrichment import (
    EnrichmentConflictError,
    PlacementSuggestion,
)
from job_finding_assistant.fakes import (
    FakeJobBoardSession,
    FakeLlmCvEnricher,
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
    enricher: FakeLlmCvEnricher | None = None,
) -> Assistant:
    return Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=FakeJobBoardSession(),
        master_cv=DiskMasterCvStore(tmp_path / "master_cv_state"),
        llm_judge=FakeLlmJudge(),
        llm_cv_tailor=FakeLlmCvTailor(),
        llm_cv_enricher=enricher or FakeLlmCvEnricher(),
        constraint_files=DiskConstraintFilesStore(tmp_path / "constraint_files_state"),
    )


def _with_master(tmp_path: Path, enricher: FakeLlmCvEnricher | None = None) -> tuple[Assistant, Path]:
    master_cv_path = tmp_path / "master_CV.yaml"
    master_cv_path.write_text(_SAMPLE_MASTER_CV, encoding="utf-8")
    assistant = _assistant(tmp_path, enricher=enricher)
    assistant.set_master_cv_path(str(master_cv_path))
    return assistant, master_cv_path


def test_submit_freeform_suggests_placement(tmp_path: Path) -> None:
    placement = PlacementSuggestion(
        section="experience",
        mode="existing",
        entry_index=0,
        label="Software Intern at Acme Corp",
    )
    enricher = FakeLlmCvEnricher(placement=placement)
    assistant, _ = _with_master(tmp_path, enricher=enricher)

    view = assistant.submit_enrichment_freeform(
        "I also led a cross-team reporting dashboard at Acme"
    )

    assert view.step == "placement"
    assert view.placement == placement
    assert view.freeform.startswith("I also led")
    assert enricher.suggest_calls == 1
    assert view.llm_unavailable_reason is None


def test_enrichment_unavailable_keeps_freeform_for_retry(tmp_path: Path) -> None:
    enricher = FakeLlmCvEnricher(available=False)
    assistant, _ = _with_master(tmp_path, enricher=enricher)

    view = assistant.submit_enrichment_freeform("Led a team")

    assert view.step == "freeform"
    assert view.freeform == "Led a team"
    assert view.llm_unavailable_reason is not None
    assert "Unavailable" in view.llm_unavailable_reason


def test_confirm_placement_starts_first_dimension(tmp_path: Path) -> None:
    assistant, _ = _with_master(tmp_path)
    assistant.submit_enrichment_freeform("Led a team")

    view = assistant.confirm_enrichment_placement()

    assert view.step == "dimension"
    assert view.current_dimension == "problem_context"
    assert view.dimension_prompt is not None


def test_dimension_answers_skip_empty_and_reach_highlights(tmp_path: Path) -> None:
    enricher = FakeLlmCvEnricher(followup=None)
    assistant, _ = _with_master(tmp_path, enricher=enricher)
    assistant.submit_enrichment_freeform("Led a team")
    assistant.confirm_enrichment_placement()

    # Answer first dimension, skip the rest
    view = assistant.submit_enrichment_dimension("Built internal tools for ops")
    assert view.step == "dimension"
    view = assistant.skip_enrichment_dimension()
    assert view.step == "dimension"
    view = assistant.skip_enrichment_dimension()
    assert view.step == "dimension"
    view = assistant.skip_enrichment_dimension()
    assert view.step == "dimension"
    view = assistant.skip_enrichment_dimension()

    assert view.step == "highlights"
    assert view.highlights is not None
    assert "Built internal tools" in view.highlights
    assert enricher.draft_calls == 1


def test_confirm_write_patches_only_target_entry_highlights(tmp_path: Path) -> None:
    highlights = [
        "Built internal tools",
        "Led cross-team delivery of a reporting dashboard",
    ]
    enricher = FakeLlmCvEnricher(followup=None, highlights=highlights)
    assistant, master_path = _with_master(tmp_path, enricher=enricher)
    assistant.submit_enrichment_freeform("Led a team")
    assistant.confirm_enrichment_placement()
    assistant.submit_enrichment_dimension("context")
    for _ in range(4):
        assistant.skip_enrichment_dimension()

    view = assistant.confirm_enrichment_write()

    assert view.step == "done"
    loaded = yaml.safe_load(master_path.read_text(encoding="utf-8"))
    experience = loaded["cv"]["sections"]["experience"][0]
    assert experience["highlights"] == highlights
    assert experience["company"] == "Acme Corp"
    assert loaded["cv"]["name"] == "Alice Example"
    assert loaded["cv"]["sections"]["skills"][0]["label"] == "Languages"
    # Snapshot rebuilt
    snap = assistant.get_candidate_files().snapshot
    assert snap is not None
    assert any("reporting dashboard" in line for line in snap.experience)


def test_confirm_write_refuses_when_master_cv_changed(tmp_path: Path) -> None:
    enricher = FakeLlmCvEnricher(followup=None)
    assistant, master_path = _with_master(tmp_path, enricher=enricher)
    assistant.submit_enrichment_freeform("Led a team")
    assistant.confirm_enrichment_placement()
    assistant.submit_enrichment_dimension("context")
    for _ in range(4):
        assistant.skip_enrichment_dimension()

    master_path.write_text(
        master_path.read_text(encoding="utf-8") + "\n# edited elsewhere\n",
        encoding="utf-8",
    )

    with pytest.raises(EnrichmentConflictError):
        assistant.confirm_enrichment_write()
    assert assistant.get_enrichment_session() is None
    # Original highlights unchanged aside from our external edit comment
    text = master_path.read_text(encoding="utf-8")
    assert "Built internal tools" in text
    assert "reporting dashboard" not in text


def test_new_entry_requires_identity_on_confirm(tmp_path: Path) -> None:
    placement = PlacementSuggestion(
        section="experience",
        mode="new",
        company="Beta Ltd",
        position="Engineer",
        start_date="2023",
        end_date="2024",
        label="Engineer at Beta Ltd",
    )
    enricher = FakeLlmCvEnricher(followup=None, placement=placement)
    assistant, master_path = _with_master(tmp_path, enricher=enricher)
    assistant.submit_enrichment_freeform("Worked at Beta")
    view = assistant.confirm_enrichment_placement(
        company="Beta Ltd",
        position="Engineer",
        start_date="2023",
        end_date="2024",
    )
    assert view.step == "dimension"
    assistant.submit_enrichment_dimension("shipped APIs")
    for _ in range(4):
        assistant.skip_enrichment_dimension()
    assistant.confirm_enrichment_write()

    loaded = yaml.safe_load(master_path.read_text(encoding="utf-8"))
    assert len(loaded["cv"]["sections"]["experience"]) == 2
    assert loaded["cv"]["sections"]["experience"][1]["company"] == "Beta Ltd"
