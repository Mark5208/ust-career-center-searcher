"""Candidate Snapshot derived from Master CV LaTeX (as written, no inferred skills)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateSnapshot:
    """Structured view of the Master CV for matching — inspectable, not hand-editable."""

    contact: str | None
    education: list[str]
    experience: list[str]
    projects: list[str]
    skills_tools: list[str]


_SECTION_RE = re.compile(
    r"\\section\*?\{([^}]*)\}(.*?)(?=\\section\*?\{|\\end\{document\}|\Z)",
    re.DOTALL | re.IGNORECASE,
)

_SECTION_ALIASES: dict[str, str] = {
    "contact": "contact",
    "education": "education",
    "experience": "experience",
    "work experience": "experience",
    "projects": "projects",
    "skills": "skills_tools",
    "skills/tools": "skills_tools",
    "tools": "skills_tools",
}


def build_candidate_snapshot(latex: str) -> CandidateSnapshot:
    """Parse section bodies from Master CV LaTeX into a Candidate Snapshot."""
    sections: dict[str, list[str]] = {}
    for match in _SECTION_RE.finditer(latex):
        title = match.group(1).strip().lower()
        body = match.group(2).strip()
        key = _SECTION_ALIASES.get(title)
        if key is None or not body:
            continue
        sections.setdefault(key, []).append(body)

    def entries(key: str) -> list[str]:
        bodies = sections.get(key, [])
        parts: list[str] = []
        for body in bodies:
            parts.extend(part.strip() for part in re.split(r"\n\s*\n", body) if part.strip())
        return parts

    contact_bodies = sections.get("contact", [])
    contact = "\n\n".join(contact_bodies) if contact_bodies else None
    return CandidateSnapshot(
        contact=contact,
        education=entries("education"),
        experience=entries("experience"),
        projects=entries("projects"),
        skills_tools=entries("skills_tools"),
    )
