"""Package contract for master-cv-authoring and the Authoring family (issue #39).

The unit under test is the on-disk package a skill loader can see — not interview
or write behaviour, and not application Python.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILLS_ROOT = _REPO_ROOT / ".agents" / "skills"
_SKILL_DIR = _SKILLS_ROOT / "master-cv-authoring"
_SKILL = _SKILL_DIR / "SKILL.md"
_SIDECAR = _SKILL_DIR / "agents" / "openai.yaml"
_PROTOCOL = _SKILLS_ROOT / "master-cv-write-protocol.md"
_PROTOCOL_SKILL_DIR = _SKILLS_ROOT / "master-cv-write-protocol"

_FAMILY_SKILL_NAMES = (
    "master-cv-authoring",
    "master-cv-content-interview",
    "master-cv-design-pins",
)

_CURSOR_ONLY_TOOLS = ("AskQuestion", "CallMcpTool", "cursor/ask_question")
_CLAUDE_ONLY_INJECTION = ("$CLAUDE_", "!`")


def _frontmatter_description(text: str) -> str:
    assert text.startswith("---\n")
    end = text.index("\n---", 3)
    for line in text[4:end].splitlines():
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    raise AssertionError("SKILL.md frontmatter has no description")


def _portable(text: str) -> None:
    for name in _CURSOR_ONLY_TOOLS:
        assert name not in text
    for token in _CLAUDE_ONLY_INJECTION:
        assert token not in text


def test_router_skill_exists() -> None:
    assert _SKILL.is_file()


def test_router_skill_is_user_invoked() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    assert "name: master-cv-authoring" in text
    assert "disable-model-invocation: true" in text
    description = _frontmatter_description(text)
    assert "\n" not in description
    assert "use when" not in description.lower()


def test_router_codex_sidecar_forbids_implicit_invocation() -> None:
    assert _SIDECAR.is_file()
    text = _SIDECAR.read_text(encoding="utf-8")
    assert "allow_implicit_invocation: false" in text


def test_router_skill_points_at_the_authoring_write_protocol() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    assert "../master-cv-write-protocol.md" in text
    assert "not a skill" in text.lower()
    assert "/master-cv-write" in text
    assert "never runs" in text.lower()


def test_router_skill_names_the_leaves() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    assert "/master-cv-content-interview" in text
    assert "/master-cv-design-pins" in text


def test_router_skill_uses_portable_wording() -> None:
    _portable(_SKILL.read_text(encoding="utf-8"))


def test_authoring_family_has_three_user_invoked_skills() -> None:
    for name in _FAMILY_SKILL_NAMES:
        skill = _SKILLS_ROOT / name / "SKILL.md"
        sidecar = _SKILLS_ROOT / name / "agents" / "openai.yaml"
        text = skill.read_text(encoding="utf-8")
        assert f"name: {name}" in text
        assert "disable-model-invocation: true" in text
        assert sidecar.is_file()
        assert "allow_implicit_invocation: false" in sidecar.read_text(encoding="utf-8")


def test_authoring_family_protocol_is_not_a_skill() -> None:
    assert _PROTOCOL.is_file()
    assert not _PROTOCOL_SKILL_DIR.exists()
    text = _PROTOCOL.read_text(encoding="utf-8")
    assert not text.startswith("---")
    assert "not a skill" in text.lower()
    assert "/master-cv-write" in text


def test_authoring_family_each_skill_points_at_the_protocol() -> None:
    for name in _FAMILY_SKILL_NAMES:
        text = (_SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")
        assert "../master-cv-write-protocol.md" in text
        assert "not a skill" in text.lower()
        assert "/master-cv-write" in text


def test_authoring_family_bodies_use_portable_wording() -> None:
    paths = [_PROTOCOL, *(_SKILLS_ROOT / name / "SKILL.md" for name in _FAMILY_SKILL_NAMES)]
    for path in paths:
        _portable(path.read_text(encoding="utf-8"))
