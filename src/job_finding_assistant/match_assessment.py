"""Match Assessment value types (Hard Constraint, Preference, Relevance, Evidence)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ConstraintOutcome = Literal["pass", "fail", "unknown"]
PreferenceBand = Literal["Strong", "Mixed", "Weak"]
RelevanceBand = Literal["Strong", "Mixed", "Weak"]


@dataclass(frozen=True)
class EvidencePair:
    """One justification unit linking sources for a judgment."""

    job_excerpt: str
    candidate_excerpt: str
    role: str


@dataclass(frozen=True)
class HardConstraintJudgment:
    """LLM Hard Constraint outcome with short reason (and optional light Evidence)."""

    outcome: ConstraintOutcome
    reason: str
    evidence: list[EvidencePair]


@dataclass(frozen=True)
class PreferenceJudgment:
    """LLM Preference band with short reason (and optional light Evidence)."""

    preference: PreferenceBand
    reason: str
    evidence: list[EvidencePair]


@dataclass(frozen=True)
class RelevanceJudgment:
    """LLM Relevance band plus Evidence pairs."""

    relevance: RelevanceBand
    evidence: list[EvidencePair]


@dataclass(frozen=True)
class MatchAssessment:
    """Full fit judgment for one Job Posting (absent row means Pending)."""

    job_posting_id: str
    hard_constraint_outcome: ConstraintOutcome
    hard_constraint_reason: str
    preference: PreferenceBand | None
    preference_reason: str
    relevance: RelevanceBand
    evidence: list[EvidencePair]
