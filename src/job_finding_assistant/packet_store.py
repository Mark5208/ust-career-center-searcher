"""Tool-managed Preparation Packet file store keyed by Job Posting."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from job_finding_assistant.preparation_packet import (
    EditSummary,
    GapItem,
    GapReport,
    GapStatus,
    PreparationPacket,
)


@dataclass(frozen=True)
class PacketPresence:
    """Flags-only view of Preparation Packet presence for Assessment Summary."""

    has_preparation_packet: bool
    stale: bool


class PacketStore:
    """Filesystem store for Gap Report / Edit Summary / Tailored YAML / PDF."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _packet_dir(self, job_posting_id: str) -> Path:
        return self._root / job_posting_id

    def save(
        self,
        job_posting_id: str,
        *,
        gap_report: GapReport,
        edit_summary: EditSummary,
        tailored_yaml: str,
        pdf_bytes: bytes | None,
        stale: bool = False,
    ) -> PreparationPacket:
        """Replace the packet for one Job Posting without leaving a half-packet.

        Writes to a sibling staging directory, then swaps via rename so a mid-run
        failure keeps the prior packet (if any) readable.
        """
        target = self._packet_dir(job_posting_id)
        staging = self._root / f".{job_posting_id}.staging"
        backup = self._root / f".{job_posting_id}.backup"
        if staging.exists():
            shutil.rmtree(staging)
        if backup.exists():
            shutil.rmtree(backup)
        staging.mkdir(parents=True)
        try:
            (staging / "gap_report.json").write_text(
                _gap_report_to_json(gap_report), encoding="utf-8"
            )
            (staging / "edit_summary.json").write_text(
                _edit_summary_to_json(edit_summary), encoding="utf-8"
            )
            (staging / "tailored.yaml").write_text(tailored_yaml, encoding="utf-8")
            if pdf_bytes is not None:
                (staging / "tailored.pdf").write_bytes(pdf_bytes)
            (staging / "meta.json").write_text(
                json.dumps({"stale": stale}), encoding="utf-8"
            )
            if target.exists():
                target.rename(backup)
            staging.rename(target)
            if backup.exists():
                shutil.rmtree(backup)
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            if not target.exists() and backup.exists():
                backup.rename(target)
            raise
        return PreparationPacket(
            job_posting_id=job_posting_id,
            gap_report=gap_report,
            edit_summary=edit_summary,
            tailored_yaml=tailored_yaml,
            pdf_bytes=pdf_bytes,
            stale=stale,
        )

    def _read_stale_flag(self, packet_dir: Path) -> bool:
        meta_path = packet_dir / "meta.json"
        if not meta_path.is_file():
            return False
        return bool(json.loads(meta_path.read_text(encoding="utf-8")).get("stale"))

    def get(self, job_posting_id: str) -> PreparationPacket | None:
        """Load one packet, or None when absent."""
        packet_dir = self._packet_dir(job_posting_id)
        yaml_path = packet_dir / "tailored.yaml"
        if not yaml_path.is_file():
            return None
        gap_report = _gap_report_from_json(
            (packet_dir / "gap_report.json").read_text(encoding="utf-8")
        )
        edit_summary = _edit_summary_from_json(
            (packet_dir / "edit_summary.json").read_text(encoding="utf-8")
        )
        tailored_yaml = yaml_path.read_text(encoding="utf-8")
        pdf_path = packet_dir / "tailored.pdf"
        pdf_bytes = pdf_path.read_bytes() if pdf_path.is_file() else None
        return PreparationPacket(
            job_posting_id=job_posting_id,
            gap_report=gap_report,
            edit_summary=edit_summary,
            tailored_yaml=tailored_yaml,
            pdf_bytes=pdf_bytes,
            stale=self._read_stale_flag(packet_dir),
        )

    def presence_flags(
        self, job_posting_ids: Iterable[str]
    ) -> dict[str, PacketPresence]:
        """Return has-packet + Stale flags without loading Gap Report / YAML / PDF."""
        flags: dict[str, PacketPresence] = {}
        for job_posting_id in job_posting_ids:
            packet_dir = self._packet_dir(job_posting_id)
            if not (packet_dir / "tailored.yaml").is_file():
                flags[job_posting_id] = PacketPresence(
                    has_preparation_packet=False, stale=False
                )
                continue
            flags[job_posting_id] = PacketPresence(
                has_preparation_packet=True,
                stale=self._read_stale_flag(packet_dir),
            )
        return flags

    def mark_stale(self, job_posting_id: str) -> None:
        """Flag an existing packet as Stale without altering artifacts."""
        packet_dir = self._packet_dir(job_posting_id)
        if not (packet_dir / "tailored.yaml").is_file():
            return
        meta_path = packet_dir / "meta.json"
        meta_path.write_text(json.dumps({"stale": True}), encoding="utf-8")

    def mark_all_stale(self) -> None:
        """Flag every stored packet as Stale."""
        if not self._root.is_dir():
            return
        for child in self._root.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                self.mark_stale(child.name)

    def delete(self, job_posting_id: str) -> None:
        """Hard-remove the packet directory for one Job Posting, if present."""
        packet_dir = self._packet_dir(job_posting_id)
        if packet_dir.exists():
            shutil.rmtree(packet_dir)


def _gap_report_to_json(report: GapReport) -> str:
    return json.dumps(
        {
            "items": [
                {
                    "requirement": item.requirement,
                    "status": item.status,
                    "evidence": item.evidence,
                    "suggestion": item.suggestion,
                }
                for item in report.items
            ]
        }
    )


def _gap_report_from_json(raw: str) -> GapReport:
    data = json.loads(raw)
    return GapReport(
        items=tuple(
            GapItem(
                requirement=item["requirement"],
                status=cast(GapStatus, item["status"]),
                evidence=item["evidence"],
                suggestion=item["suggestion"],
            )
            for item in data.get("items", [])
        )
    )


def _edit_summary_to_json(summary: EditSummary) -> str:
    return json.dumps(
        {
            "omissions": list(summary.omissions),
            "section_order": list(summary.section_order),
            "cross_role_chronology": list(summary.cross_role_chronology),
            "summary_rewrite": list(summary.summary_rewrite),
            "pin_notes": list(summary.pin_notes),
            "material_rephrases": list(summary.material_rephrases),
        }
    )


def _edit_summary_from_json(raw: str) -> EditSummary:
    data = json.loads(raw)
    return EditSummary(
        omissions=tuple(data.get("omissions", ())),
        section_order=tuple(data.get("section_order", ())),
        cross_role_chronology=tuple(data.get("cross_role_chronology", ())),
        summary_rewrite=tuple(data.get("summary_rewrite", ())),
        pin_notes=tuple(data.get("pin_notes", ())),
        material_rephrases=tuple(data.get("material_rephrases", ())),
    )


# Re-export for callers that import PacketStore from this module.
__all__ = ["PacketPresence", "PacketStore"]
