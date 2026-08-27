"""Package contract for master-cv-design-pins (issue #38).

The unit under test is the on-disk skill a loader can see — not interview
or write behaviour, and not application Python.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILLS_ROOT = _REPO_ROOT / ".agents" / "skills"
_SKILL_DIR = _SKILLS_ROOT / "master-cv-design-pins"
_SKILL = _SKILL_DIR / "SKILL.md"
_SIDECAR = _SKILL_DIR / "agents" / "openai.yaml"

_CURSOR_ONLY_TOOLS = ("AskQuestion", "CallMcpTool", "cursor/ask_question")
_CLAUDE_ONLY_INJECTION = ("$CLAUDE_", "!`")


def _frontmatter_description(text: str) -> str:
    assert text.startswith("---\n")
    end = text.index("\n---", 3)
    for line in text[4:end].splitlines():
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    raise AssertionError("SKILL.md frontmatter has no description")


def test_design_pins_skill_exists() -> None:
    assert _SKILL.is_file()


def test_design_pins_skill_is_user_invoked() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    assert "name: master-cv-design-pins" in text
    assert "disable-model-invocation: true" in text
    description = _frontmatter_description(text)
    assert "\n" not in description
    assert "use when" not in description.lower()


def test_design_pins_codex_sidecar_forbids_implicit_invocation() -> None:
    assert _SIDECAR.is_file()
    text = _SIDECAR.read_text(encoding="utf-8")
    assert "allow_implicit_invocation: false" in text


def test_design_pins_skill_points_at_the_authoring_write_protocol() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    assert "../master-cv-write-protocol.md" in text
    assert "not a skill" in text.lower()
    assert "/master-cv-write" in text


def test_design_pins_skill_uses_portable_wording() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    for name in _CURSOR_ONLY_TOOLS:
        assert name not in text
    for token in _CLAUDE_ONLY_INJECTION:
        assert token not in text
