"""PacketStore: general save/get round-trip and meta-field preservation."""

from pathlib import Path

from job_finding_assistant.packet_store import PacketStore
from job_finding_assistant.preparation_packet import EditSummary, GapReport


def test_save_and_get_round_trip_pdf_missing_reasons_and_mark_stale_preserves_them(
    tmp_path: Path,
) -> None:
    store = PacketStore(tmp_path / "packets")
    store.save(
        "no-pdf",
        gap_report=GapReport(),
        edit_summary=EditSummary(),
        tailored_yaml="cv:\n  name: A\n",
        pdf_bytes=None,
        pdf_missing_reasons=("cv.sections.experience.0.position: This field is required.",),
    )

    packet = store.get("no-pdf")
    assert packet is not None
    assert packet.pdf_missing_reasons == (
        "cv.sections.experience.0.position: This field is required.",
    )

    store.mark_stale("no-pdf")

    reloaded = store.get("no-pdf")
    assert reloaded is not None
    assert reloaded.stale is True
    assert reloaded.pdf_missing_reasons == (
        "cv.sections.experience.0.position: This field is required.",
    )
