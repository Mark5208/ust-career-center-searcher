"""Preparation Packet value types (Gap Report, Edit Summary, Tailor result)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

GapStatus = Literal["missing", "partial"]


@dataclass(frozen=True)
class GapItem:
    """One Gap Report row: requirement, status, Master CV Evidence, Suggestion."""

    requirement: str
    status: GapStatus
    evidence: str
    suggestion: str


@dataclass(frozen=True)
class GapReport:
    """Gaps vs the Job Posting built at Prepare (empty is valid)."""

    items: tuple[GapItem, ...] = ()

    @property
    def note(self) -> str | None:
        """Human note when there are no required gaps."""
        if self.items:
            return None
        return "No required gaps identified"


@dataclass(frozen=True)
class EditSummary:
    """Grouped Master CV → Tailored CV audit (never JD gaps)."""

    omissions: tuple[str, ...] = ()
    section_order: tuple[str, ...] = ()
    cross_role_chronology: tuple[str, ...] = ()
    summary_rewrite: tuple[str, ...] = ()
    pin_notes: tuple[str, ...] = ()
    material_rephrases: tuple[str, ...] = ()

    def has_material_edits(self) -> bool:
        return bool(
            self.omissions
            or self.section_order
            or self.cross_role_chronology
            or self.summary_rewrite
            or self.pin_notes
            or self.material_rephrases
        )

    def grouped_sections(self) -> list[tuple[str, tuple[str, ...]]]:
        """Return non-empty groups in review order with human headings."""
        groups = (
            ("Omissions", self.omissions),
            ("Section order", self.section_order),
            ("Cross-role chronology", self.cross_role_chronology),
            ("Summary rewrite", self.summary_rewrite),
            ("Pin notes", self.pin_notes),
            ("Material rephrases", self.material_rephrases),
        )
        return [(heading, items) for heading, items in groups if items]


@dataclass(frozen=True)
class TailorResult:
    """One Prepare-pass tailor output before PDF render."""

    gap_report: GapReport
    edit_summary: EditSummary
    tailored_yaml: str


@dataclass(frozen=True)
class PreparationPacket:
    """Tool-managed prepare-to-apply artifacts for one Job Posting."""

    job_posting_id: str
    gap_report: GapReport
    edit_summary: EditSummary
    tailored_yaml: str
    pdf_bytes: bytes | None
    stale: bool = False

    @property
    def pdf_missing(self) -> bool:
        return self.pdf_bytes is None
