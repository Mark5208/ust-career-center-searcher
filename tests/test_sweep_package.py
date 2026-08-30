"""Package contract for sweep (issue #71).

The unit under test is the on-disk package a skill loader can see — not leftover
classification, land, retarget, or spent-delete behaviour, and not application
Python.
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILLS_ROOT = _REPO_ROOT / ".agents" / "skills"
_SKILL_DIR = _SKILLS_ROOT / "sweep"
_SKILL = _SKILL_DIR / "SKILL.md"
_SIDECAR = _SKILL_DIR / "agents" / "openai.yaml"
_LOCKFILE = _REPO_ROOT / "skills-lock.json"
_AGENTS_MD = _REPO_ROOT / "AGENTS.md"

_PICKER_DESCRIPTION = (
    "After a wayfinder map is done, classify leftovers and janitor spent throwaways."
)

_CURSOR_ONLY_TOOLS = ("AskQuestion", "CallMcpTool", "cursor/ask_question")
_CLAUDE_ONLY_INJECTION = ("$CLAUDE_", "!`")
_DART_TOB_NAMES = ("SAFE_TO_DELETE", "UNPUSHED_WORK", "ahead=0")

_CLIENT_COPIES = (
    _REPO_ROOT / ".cursor" / "skills" / "sweep",
    _REPO_ROOT / ".codex" / "skills" / "sweep",
    _REPO_ROOT / ".claude" / "skills" / "sweep",
)


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


def test_sweep_skill_exists() -> None:
    assert _SKILL.is_file()
    assert _SIDECAR.is_file()


def test_sweep_skill_is_user_invoked() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    assert "name: sweep" in text
    assert "disable-model-invocation: true" in text
    description = _frontmatter_description(text)
    assert description == _PICKER_DESCRIPTION
    assert "\n" not in description
    assert "use when" not in description.lower()


def test_sweep_codex_sidecar_matches_user_invoked_pair() -> None:
    text = _SIDECAR.read_text(encoding="utf-8")
    assert "display_name: Sweep" in text or 'display_name: "Sweep"' in text
    assert _PICKER_DESCRIPTION in text
    assert "allow_implicit_invocation: false" in text


def test_sweep_has_one_project_copy() -> None:
    for path in _CLIENT_COPIES:
        assert not path.exists()
    extras = [
        path
        for path in _SKILLS_ROOT.iterdir()
        if path.name.startswith("sweep") and path != _SKILL_DIR
    ]
    assert extras == []
    assert _SKILL_DIR.is_dir()
    sibling_md = [
        path
        for path in _SKILL_DIR.iterdir()
        if path.suffix == ".md" and path.name != "SKILL.md"
    ]
    assert sibling_md == []


def test_sweep_is_not_in_the_skills_lockfile() -> None:
    payload = json.loads(_LOCKFILE.read_text(encoding="utf-8"))
    assert "sweep" not in payload.get("skills", {})


def test_agents_md_has_no_sweep_pointer() -> None:
    text = _AGENTS_MD.read_text(encoding="utf-8")
    assert "/sweep" not in text
    assert "skills/sweep" not in text


def test_sweep_skill_uses_portable_wording() -> None:
    _portable(_SKILL.read_text(encoding="utf-8"))
    _portable(_SIDECAR.read_text(encoding="utf-8"))


def test_sweep_skill_omits_dart_and_tob_classifier_names() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    for name in _DART_TOB_NAMES:
        assert name not in text
