"""Match Assessment value types (Hard Constraints, Relevance, Evidence)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from job_finding_assistant.hard_constraints import ConstraintOutcome, ConstraintResult

RelevanceBand = Literal["Strong", "Mixed", "Weak"]


@dataclass(frozen=True)
class EvidencePair:
    """One justification unit linking Job Posting text to Candidate Snapshot text."""

    job_excerpt: str
    candidate_excerpt: str
    role: str


@dataclass(frozen=True)
class JudgeResult:
    """LLM Relevance band plus Evidence pairs."""

    relevance: RelevanceBand
    evidence: list[EvidencePair]


@dataclass(frozen=True)
class NamedConstraintResult:
    """Hard Constraint check labelled by name for Match Assessment storage."""

    name: str
    result: ConstraintResult


@dataclass(frozen=True)
class MatchAssessment:
    """Full fit judgment for one Job Posting."""

    job_posting_id: str
    hard_constraint_outcome: ConstraintOutcome
    hard_constraints: list[NamedConstraintResult]
    relevance: RelevanceBand
    evidence: list[EvidencePair]
