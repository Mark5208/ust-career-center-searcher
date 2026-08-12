"""Tailored YAML validation against RenderCV's real schema (ADR-0013)."""

from __future__ import annotations

from job_finding_assistant.rendercv_validation import (
    strip_assistant_metadata,
    validate_tailored_yaml,
)

_VALID_CV = """\
cv:
  name: Test Candidate
  sections:
    experience:
      - company: Example
        position: Platform engineer
        highlights:
          - Built Python services
"""

_MISSING_POSITION_CV = """\
cv:
  name: Test Candidate
  sections:
    experience:
      - company: Example
        highlights:
          - Built Python services
"""


def test_validate_tailored_yaml_accepts_valid_cv() -> None:
    result = validate_tailored_yaml(_VALID_CV)

    assert result.valid is True
    assert result.errors == ()


def test_validate_tailored_yaml_reports_schema_errors_for_missing_field() -> None:
    result = validate_tailored_yaml(_MISSING_POSITION_CV)

    assert result.valid is False
    assert result.errors
    assert any("position" in error for error in result.errors)
    assert any("required" in error.lower() for error in result.errors)


def test_validate_tailored_yaml_reports_malformed_yaml_syntax() -> None:
    result = validate_tailored_yaml("not: valid: yaml: [")

    assert result.valid is False
    assert result.errors


def test_validate_tailored_yaml_ignores_assistant_metadata() -> None:
    """assistant.pinned_section_order is legitimate Tailored CV metadata (ADR-0009);
    RenderCV's real schema rejects unknown top-level fields, so validation must
    strip it first — the same view PdfRenderer already renders from."""
    with_metadata = _VALID_CV + "assistant:\n  pinned_section_order:\n    - experience\n"

    result = validate_tailored_yaml(with_metadata)

    assert result.valid is True
    assert result.errors == ()


def test_strip_assistant_metadata_removes_top_level_assistant_key() -> None:
    with_metadata = _VALID_CV + "assistant:\n  pinned_section_order:\n    - experience\n"

    stripped = strip_assistant_metadata(with_metadata)

    assert "assistant" not in stripped
    assert "pinned_section_order" not in stripped
    assert "Platform engineer" in stripped


def test_strip_assistant_metadata_is_noop_without_assistant_key() -> None:
    stripped = strip_assistant_metadata(_VALID_CV)

    assert "Platform engineer" in stripped
