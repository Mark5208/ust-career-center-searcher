"""Package contract for the project wayfinder map-done hint (issue #72).

The unit under test is the on-disk lockfile-vendored wayfinder copy a skill
loader can see — not a live wayfinder run, and not application Python.

After a skills update restores upstream wayfinder, re-apply the one
work-through map-done hint line so these tests pass. Do not freeze the
lockfile hash.
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILLS_ROOT = _REPO_ROOT / ".agents" / "skills"
_SKILL = _SKILLS_ROOT / "wayfinder" / "SKILL.md"
_LOCKFILE = _REPO_ROOT / "skills-lock.json"

_PERMISSION_HINT = "You may type /sweep."


def _heading_section(text: str, heading: str) -> str:
    start = text.index(heading)
    rest = text[start + len(heading) :]
    next_heading = rest.find("\n### ")
    if next_heading == -1:
        return rest
    return rest[:next_heading]


def test_wayfinder_work_through_map_done_hints_sweep_permission() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    work_through = _heading_section(text, "### Work through the map")
    assert _PERMISSION_HINT in work_through
    assert "no open tickets" in work_through
    assert "no remaining **Not yet specified** fog that still needs a ticket" in work_through


def test_wayfinder_charting_never_mentions_sweep() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    charting = _heading_section(text, "### Chart the map")
    assert "/sweep" not in charting


def test_wayfinder_does_not_say_run_sweep() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    assert "Run /sweep" not in text


def test_wayfinder_stays_in_the_skills_lockfile() -> None:
    payload = json.loads(_LOCKFILE.read_text(encoding="utf-8"))
    assert "wayfinder" in payload.get("skills", {})
