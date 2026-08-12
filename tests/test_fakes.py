"""Direct tests for test-double correctness (fakes.py) — not Assistant behavior."""

from __future__ import annotations

import pytest

from job_finding_assistant.fakes import FakeLlmCvTailor
from job_finding_assistant.preparation_packet import EditSummary, GapReport, TailorResult


def _result(name: str) -> TailorResult:
    return TailorResult(
        gap_report=GapReport(),
        edit_summary=EditSummary(),
        tailored_yaml=f"cv:\n  name: {name}\n",
    )


def test_fake_llm_cv_tailor_single_result_repeats_for_any_number_of_calls() -> None:
    tailor = FakeLlmCvTailor(result=_result("A"))

    for _ in range(3):
        result = tailor.tailor(
            master_cv_yaml="",
            candidate_snapshot=None,  # type: ignore[arg-type]
            job_detail_fields={},
            relevance_evidence=[],
            hard_constraint_outcome="unknown",
            hard_constraint_reason="",
        )
        assert result.tailored_yaml == "cv:\n  name: A\n"


def test_fake_llm_cv_tailor_results_sequence_raises_when_called_past_the_scripted_count() -> (
    None
):
    """A scripted `results=` sequence is a strict contract: calling `tailor()` more
    times than scripted must fail loudly (e.g. a regression making Prepare's one
    bounded retry unbounded), not silently replay the last result."""
    tailor = FakeLlmCvTailor(results=[_result("A"), _result("B")])
    kwargs: dict[str, object] = {
        "master_cv_yaml": "",
        "candidate_snapshot": None,
        "job_detail_fields": {},
        "relevance_evidence": [],
        "hard_constraint_outcome": "unknown",
        "hard_constraint_reason": "",
    }

    tailor.tailor(**kwargs)  # type: ignore[arg-type]
    tailor.tailor(**kwargs)  # type: ignore[arg-type]

    with pytest.raises(AssertionError):
        tailor.tailor(**kwargs)  # type: ignore[arg-type]
