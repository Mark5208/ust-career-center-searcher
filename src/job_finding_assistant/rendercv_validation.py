"""Validate Tailored CV YAML against RenderCV's own schema (ADR-0013).

Distinct step from PDF rendering: Prepare calls this before ever invoking
``PdfRenderer.render_pdf`` so a schema-invalid Tailored YAML is caught with a
short, per-problem reason instead of surfacing as a bare missing PDF.
"""

from __future__ import annotations

from dataclasses import dataclass

from rendercv.exception import RenderCVUserValidationError, RenderCVValidationError
from rendercv.schema.rendercv_model_builder import build_rendercv_dictionary_and_model


@dataclass(frozen=True)
class TailoredYamlValidation:
    """Outcome of validating Tailored CV YAML against RenderCV's real schema."""

    valid: bool
    errors: tuple[str, ...] = ()


def validate_tailored_yaml(tailored_yaml: str) -> TailoredYamlValidation:
    """Return valid=True, or valid=False with one short line per schema problem.

    Validates the same metadata-stripped view PdfRenderer renders from, so a
    legitimate ``assistant.pinned_section_order`` (ADR-0009) is never mistaken
    for a schema error.
    """
    stripped = strip_assistant_metadata(tailored_yaml)
    try:
        build_rendercv_dictionary_and_model(stripped)
    except RenderCVUserValidationError as exc:
        return TailoredYamlValidation(
            valid=False,
            errors=tuple(_format_error(error) for error in exc.validation_errors),
        )
    return TailoredYamlValidation(valid=True)


def _format_error(error: RenderCVValidationError) -> str:
    location = ".".join(error.schema_location) if error.schema_location else "schema"
    return f"{location}: {error.message}"


def strip_assistant_metadata(yaml_text: str) -> str:
    """Drop optional top-level ``assistant.*`` metadata (not part of RenderCV's schema).

    Shared by the validator and ``PdfRenderer`` so both see the same YAML; returns
    the input unchanged when it does not parse as a YAML mapping.
    """
    try:
        import yaml
    except ImportError:  # pragma: no cover
        return yaml_text
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return yaml_text
    if not isinstance(data, dict):
        return yaml_text
    data.pop("assistant", None)
    return yaml.safe_dump(data, sort_keys=False)
