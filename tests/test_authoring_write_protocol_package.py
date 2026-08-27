"""Package contract for the shared Authoring write protocol (issue #36).

The unit under test is the on-disk file a skill loader can see — not interview
or write behaviour, and not application Python.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILLS_ROOT = _REPO_ROOT / ".agents" / "skills"
_PROTOCOL = _SKILLS_ROOT / "master-cv-write-protocol.md"
_SKILL_DIR = _SKILLS_ROOT / "master-cv-write-protocol"

_CURSOR_ONLY_TOOLS = ("AskQuestion", "CallMcpTool", "cursor/ask_question")
_CLAUDE_ONLY_INJECTION = ("$CLAUDE_", "!`")


def test_authoring_write_protocol_exists_as_a_plain_file() -> None:
    assert _PROTOCOL.is_file()
    assert not _SKILL_DIR.exists()


def test_authoring_write_protocol_is_not_a_skill() -> None:
    text = _PROTOCOL.read_text(encoding="utf-8")
    assert not text.startswith("---")
    assert not (_SKILL_DIR / "SKILL.md").exists()
    assert not (_SKILL_DIR / "agents" / "openai.yaml").exists()


def test_authoring_write_protocol_says_it_is_not_invoked_as_a_skill() -> None:
    text = _PROTOCOL.read_text(encoding="utf-8")
    assert "not a skill" in text.lower()
    assert "/master-cv-write" in text


def test_authoring_write_protocol_uses_portable_wording() -> None:
    text = _PROTOCOL.read_text(encoding="utf-8")
    for name in _CURSOR_ONLY_TOOLS:
        assert name not in text
    for token in _CLAUDE_ONLY_INJECTION:
        assert token not in text
