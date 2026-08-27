"""Assistant seam: empty catalog yields no Assessment Summaries."""

from pathlib import Path

from job_finding_assistant.assistant import Assistant
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.fakes import (
    FakeConstraintFilesStore,
    FakeJobBoardSession,
    FakeLlmCvTailor,
    FakeLlmJudge,
    FakeMasterCvStore,
)


def test_assistant_catalog_load_is_empty_when_catalog_has_no_job_postings(
    tmp_path: Path,
) -> None:
    catalog_store = CatalogStore(tmp_path / "catalog.db")
    assistant = Assistant(
        catalog_store=catalog_store,
        job_board=FakeJobBoardSession(),
        master_cv=FakeMasterCvStore(),
        llm_judge=FakeLlmJudge(),
        llm_cv_tailor=FakeLlmCvTailor(),
        constraint_files=FakeConstraintFilesStore(),
    )

    catalog = assistant.load_assessment_summary_catalog()

    assert catalog.rows == []
