"""PacketStore: flags-only batch presence for Assessment Summary listing."""

from pathlib import Path

from job_finding_assistant.packet_store import PacketPresence, PacketStore
from job_finding_assistant.preparation_packet import EditSummary, GapReport


def test_presence_flags_reads_exists_and_stale_without_full_packet(
    tmp_path: Path,
) -> None:
    store = PacketStore(tmp_path / "packets")
    store.save(
        "with-packet",
        gap_report=GapReport(),
        edit_summary=EditSummary(),
        tailored_yaml="cv:\n  name: A\n",
        pdf_bytes=None,
        stale=False,
    )
    store.save(
        "stale-packet",
        gap_report=GapReport(),
        edit_summary=EditSummary(),
        tailored_yaml="cv:\n  name: B\n",
        pdf_bytes=None,
        stale=True,
    )

    flags = store.presence_flags(["with-packet", "stale-packet", "missing"])

    assert flags == {
        "with-packet": PacketPresence(has_preparation_packet=True, stale=False),
        "stale-packet": PacketPresence(has_preparation_packet=True, stale=True),
        "missing": PacketPresence(has_preparation_packet=False, stale=False),
    }
