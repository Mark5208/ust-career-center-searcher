"""Rule-based Hard Constraints against Preferences (pure; no LLM)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from job_finding_assistant.preferences import GapTolerance, Preferences

ConstraintOutcome = Literal["pass", "fail", "unknown"]


@dataclass(frozen=True)
class ConstraintResult:
    """One Hard Constraint check with a short reason."""

    outcome: ConstraintOutcome
    reason: str


def evaluate_location(
    *,
    preferences: Preferences,
    work_location: str | None,
) -> ConstraintResult:
    """Location Hard Constraint: match Preferences locations or accepted remote."""
    if not preferences.locations:
        return ConstraintResult(outcome="unknown", reason="No acceptable locations set")

    text = (work_location or "").strip()
    if not text:
        return ConstraintResult(
            outcome="unknown",
            reason="Work location missing or unclear",
        )

    accepted = preferences.locations
    remote_accepted = any(loc.strip().lower() == "remote" for loc in accepted)
    if remote_accepted and _is_clearly_remote(text):
        return ConstraintResult(
            outcome="pass",
            reason="Work location is remote and remote is accepted",
        )

    for location in accepted:
        needle = location.strip()
        if not needle:
            continue
        if needle.lower() in text.lower():
            return ConstraintResult(
                outcome="pass",
                reason=f"Work location matches accepted location {needle}",
            )

    return ConstraintResult(
        outcome="fail",
        reason=f"Work location {text} is not among acceptable locations",
    )


def evaluate_language(
    *,
    preferences: Preferences,
    speaking: str | None,
    writing: str | None,
) -> ConstraintResult:
    """Language Hard Constraint: every hard-required language must be in Preferences."""
    if not preferences.languages:
        return ConstraintResult(outcome="unknown", reason="No languages set in Preferences")

    required = _required_languages(speaking, writing)
    if required is None:
        return ConstraintResult(
            outcome="unknown",
            reason="Language requirements missing or unclear",
        )
    if not required:
        return ConstraintResult(
            outcome="pass",
            reason="No hard language requirements stated",
        )

    known = {item.language.strip().lower() for item in preferences.languages if item.language.strip()}
    missing = [lang for lang in required if lang.lower() not in known]
    if missing:
        return ConstraintResult(
            outcome="fail",
            reason=f"Missing required language(s): {', '.join(missing)}",
        )
    return ConstraintResult(
        outcome="pass",
        reason=f"All required languages present: {', '.join(required)}",
    )


def evaluate_gap_tolerance(
    *,
    preferences: Preferences,
    employment_period: str | None,
) -> ConstraintResult:
    """Gap Tolerance Hard Constraint vs Employment Period study interruption."""
    if preferences.gap_tolerance is None:
        return ConstraintResult(outcome="unknown", reason="Gap Tolerance unset")

    needed = _interruption_needed(employment_period)
    if needed is None:
        return ConstraintResult(
            outcome="unknown",
            reason="Employment period impact unclear",
        )

    tolerated = _tolerance_rank(preferences.gap_tolerance)
    if needed <= tolerated:
        return ConstraintResult(
            outcome="pass",
            reason=(
                f"Employment period within Gap Tolerance "
                f"{preferences.gap_tolerance.value}"
            ),
        )
    return ConstraintResult(
        outcome="fail",
        reason=(
            f"Employment period exceeds Gap Tolerance "
            f"{preferences.gap_tolerance.value}"
        ),
    )


def overall_hard_constraint(
    results: list[ConstraintResult],
) -> ConstraintOutcome:
    """Fail if any fails; else pass if all that apply pass; else unknown."""
    if any(result.outcome == "fail" for result in results):
        return "fail"
    applicable = [result for result in results if result.outcome != "unknown"]
    if applicable and all(result.outcome == "pass" for result in applicable):
        return "pass"
    return "unknown"


def evaluate_all(
    *,
    preferences: Preferences,
    detail_fields: dict[str, str],
) -> list[tuple[str, ConstraintResult]]:
    """Run language, location, and Gap Tolerance Hard Constraints from detail fields."""
    return [
        (
            "language",
            evaluate_language(
                preferences=preferences,
                speaking=detail_fields.get("Language Requirement (Speaking)"),
                writing=detail_fields.get("Language Requirement (Writing)"),
            ),
        ),
        (
            "location",
            evaluate_location(
                preferences=preferences,
                work_location=detail_fields.get("Work Location"),
            ),
        ),
        (
            "gap_tolerance",
            evaluate_gap_tolerance(
                preferences=preferences,
                employment_period=detail_fields.get("Employment Period"),
            ),
        ),
    ]


def _is_clearly_remote(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in ("remote", "work from home", "wfh", "home-based")
    )


def _required_languages(speaking: str | None, writing: str | None) -> list[str] | None:
    """Return hard-required languages, empty list if none hard, None if unclear/missing."""
    chunks = [text.strip() for text in (speaking, writing) if text and text.strip()]
    if not chunks:
        return None

    required: list[str] = []
    saw_hard_signal = False
    for chunk in chunks:
        lowered = chunk.lower()
        # Preferred / vague alone is not a hard require.
        if _is_only_preferred_or_vague(lowered):
            continue
        saw_hard_signal = True
        for name in _extract_language_names(chunk):
            if name not in required:
                required.append(name)

    if not saw_hard_signal:
        # Preferred/vague wording is not a hard require → vacuous (no requirements).
        return []
    if not required:
        return None
    return required


_LANGUAGE_NAMES = (
    "English",
    "Cantonese",
    "Mandarin",
    "Putonghua",
    "Chinese",
    "Japanese",
    "Korean",
    "French",
    "German",
    "Spanish",
)


def _extract_language_names(text: str) -> list[str]:
    found: list[str] = []
    for name in _LANGUAGE_NAMES:
        if re.search(rf"\b{re.escape(name)}\b", text, flags=re.IGNORECASE):
            # Normalize Putonghua → Mandarin for preference matching convenience? Keep as written.
            label = "Mandarin" if name.lower() == "putonghua" else name
            if label not in found:
                found.append(label)
    return found


def _is_only_preferred_or_vague(lowered: str) -> bool:
    if not lowered or lowered in {"n/a", "na", "nil", "-", "none", "not specified"}:
        return True
    preferred_markers = ("prefer", "preferred", "advantage", "asset", "bonus")
    hard_markers = ("require", "must", "fluent", "native", "compulsory", "essential")
    return any(marker in lowered for marker in preferred_markers) and not any(
        marker in lowered for marker in hard_markers
    )


def _tolerance_rank(tolerance: GapTolerance) -> int:
    return {
        GapTolerance.NONE: 0,
        GapTolerance.SEMESTER: 1,
        GapTolerance.YEAR: 2,
        GapTolerance.ANY: 3,
    }[tolerance]


def _interruption_needed(employment_period: str | None) -> int | None:
    """Map Employment Period text to interruption rank; None if unclear."""
    text = (employment_period or "").strip()
    if not text:
        return None
    lowered = text.lower()

    if any(token in lowered for token in ("permanent", "full time", "full-time")):
        return 3  # more than a year / ongoing → needs Any
    if any(token in lowered for token in ("part-time", "part time", "flexible", "no gap")):
        return 0

    months = _extract_months(lowered)
    if months is not None:
        if months <= 4:
            return 1  # Semester
        if months <= 12:
            return 2  # Year
        return 3

    if any(token in lowered for token in ("summer", "semester", "internship", "few months")):
        return 1
    if any(token in lowered for token in ("one year", "1 year", "a year", "12 months")):
        return 2

    return None


def _extract_months(lowered: str) -> int | None:
    match = re.search(r"(\d+)\s*-\s*(\d+)\s*months?", lowered)
    if match:
        return max(int(match.group(1)), int(match.group(2)))
    match = re.search(r"(\d+)\s*months?", lowered)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)\s*years?", lowered)
    if match:
        return int(match.group(1)) * 12
    return None
