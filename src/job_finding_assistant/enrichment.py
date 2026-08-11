"""Master CV Enrichment types and atomic Master CV entry patch (ADR-0017)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

ENRICHMENT_DIMENSIONS: tuple[str, ...] = (
    "problem_context",
    "technical_work",
    "collaboration_leadership",
    "domain_impact",
    "outcomes_metrics",
)

DIMENSION_PROMPTS: dict[str, str] = {
    "problem_context": "What problem or context were you working in?",
    "technical_work": "What technical work did you do?",
    "collaboration_leadership": "How did you collaborate or lead?",
    "domain_impact": "What domain or business impact did this have?",
    "outcomes_metrics": "What outcomes or metrics can you share?",
}

EnrichmentStep = Literal[
    "freeform",
    "placement",
    "dimension",
    "followup",
    "highlights",
    "done",
]

SectionName = Literal["experience", "projects", "education"]


@dataclass(frozen=True)
class PlacementSuggestion:
    """LLM-suggested Master CV placement; user must confirm before dimension steps."""

    section: SectionName
    mode: Literal["existing", "new"]
    entry_index: int | None = None
    company: str | None = None
    position: str | None = None
    name: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    label: str = ""


@dataclass
class EnrichmentSessionView:
    """Ephemeral Enrichment session projection for UI / tests."""

    step: EnrichmentStep
    freeform: str = ""
    placement: PlacementSuggestion | None = None
    current_dimension: str | None = None
    dimension_prompt: str | None = None
    followup_prompt: str | None = None
    dimension_answers: dict[str, str] = field(default_factory=dict)
    highlights: list[str] | None = None
    llm_unavailable_reason: str | None = None
    error: str | None = None


class EnrichmentError(Exception):
    """Enrichment flow cannot proceed."""


class EnrichmentConflictError(EnrichmentError):
    """Master CV changed since Enrichment session start; restart required."""


def section_key_in_yaml(sections: dict[str, Any], section: SectionName) -> str | None:
    """Return the actual sections map key for a logical section name."""
    aliases = {
        "experience": {"experience", "work experience"},
        "projects": {"projects"},
        "education": {"education"},
    }
    wanted = aliases[section]
    for key in sections:
        if str(key).strip().lower() in wanted:
            return str(key)
    return None


def existing_highlights(
    yaml_text: str, *, section: SectionName, entry_index: int
) -> list[str]:
    """Return highlights list for an existing entry (empty if none)."""
    loaded = yaml.safe_load(yaml_text)
    if not isinstance(loaded, dict):
        return []
    cv = loaded.get("cv")
    if not isinstance(cv, dict):
        return []
    sections = cv.get("sections")
    if not isinstance(sections, dict):
        return []
    key = section_key_in_yaml(sections, section)
    if key is None:
        return []
    entries = sections.get(key)
    if not isinstance(entries, list) or entry_index < 0 or entry_index >= len(entries):
        return []
    entry = entries[entry_index]
    if not isinstance(entry, dict):
        return []
    highlights = entry.get("highlights")
    if not isinstance(highlights, list):
        return []
    return [str(item) for item in highlights if str(item).strip()]


def patch_master_cv_entry(
    yaml_text: str,
    *,
    placement: PlacementSuggestion,
    highlights: list[str],
) -> str:
    """Return YAML with only the target entry patched (highlights; identity if new)."""
    loaded = yaml.safe_load(yaml_text)
    if not isinstance(loaded, dict):
        raise EnrichmentError("Master CV YAML must be a mapping")
    cv = loaded.get("cv")
    if not isinstance(cv, dict):
        raise EnrichmentError("Master CV YAML must include a cv mapping")
    sections = cv.get("sections")
    if sections is None:
        sections = {}
        cv["sections"] = sections
    if not isinstance(sections, dict):
        raise EnrichmentError("cv.sections must be a mapping")

    key = section_key_in_yaml(sections, placement.section)
    if key is None:
        raise EnrichmentError(
            f"Section {placement.section!r} not found — Enrichment cannot add section types"
        )

    entries = sections.get(key)
    if not isinstance(entries, list):
        raise EnrichmentError(f"Section {key!r} must be a list")

    if placement.mode == "existing":
        if placement.entry_index is None or not (
            0 <= placement.entry_index < len(entries)
        ):
            raise EnrichmentError("Existing placement entry_index is invalid")
        entry = entries[placement.entry_index]
        if not isinstance(entry, dict):
            raise EnrichmentError("Target entry must be a mapping")
        entry["highlights"] = list(highlights)
    else:
        entries.append(_new_entry_dict(placement, highlights))

    return yaml.safe_dump(loaded, sort_keys=False, allow_unicode=True)


def _new_entry_dict(
    placement: PlacementSuggestion, highlights: list[str]
) -> dict[str, Any]:
    if placement.section == "experience":
        entry: dict[str, Any] = {
            "company": placement.company or "",
            "position": placement.position or "",
            "highlights": list(highlights),
        }
    elif placement.section == "projects":
        entry = {
            "name": placement.name or "",
            "highlights": list(highlights),
        }
    else:
        entry = {
            "institution": placement.company or placement.name or "",
            "highlights": list(highlights),
        }
    if placement.start_date:
        entry["start_date"] = placement.start_date
    if placement.end_date:
        entry["end_date"] = placement.end_date
    return entry


def atomic_write_text(path: Path, text: str) -> None:
    """Write text via temp file then replace (atomic on same filesystem)."""
    path = Path(path)
    tmp = path.with_name(path.name + ".enrichment-tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
