"""Candidate Snapshot derived from Master CV RenderCV YAML (as written, no inferred skills)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


@dataclass(frozen=True)
class CandidateSnapshot:
    """Structured view of the Master CV for matching — inspectable, not hand-editable."""

    contact: str | None
    education: list[str]
    experience: list[str]
    projects: list[str]
    skills_tools: list[str]


_SECTION_ALIASES: dict[str, str] = {
    "education": "education",
    "experience": "experience",
    "work experience": "experience",
    "projects": "projects",
    "skills": "skills_tools",
    "skills/tools": "skills_tools",
    "tools": "skills_tools",
}


class InvalidMasterCvError(ValueError):
    """Master CV YAML is unreadable as RenderCV content for Snapshot rebuild."""


def build_candidate_snapshot(yaml_text: str) -> CandidateSnapshot:
    """Parse RenderCV YAML into a Candidate Snapshot.

    Raises InvalidMasterCvError when the text is not valid RenderCV-shaped YAML.
    """
    try:
        loaded = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise InvalidMasterCvError("Master CV YAML is invalid") from exc

    if not isinstance(loaded, dict):
        raise InvalidMasterCvError("Master CV YAML must be a mapping")
    cv = loaded.get("cv")
    if not isinstance(cv, dict):
        raise InvalidMasterCvError("Master CV YAML must include a cv mapping")

    contact = _format_contact(cv)
    sections = cv.get("sections")
    if sections is None:
        sections = {}
    if not isinstance(sections, dict):
        raise InvalidMasterCvError("cv.sections must be a mapping when present")

    buckets: dict[str, list[str]] = {
        "education": [],
        "experience": [],
        "projects": [],
        "skills_tools": [],
    }
    for title, entries in sections.items():
        key = _SECTION_ALIASES.get(str(title).strip().lower())
        if key is None:
            continue
        if not isinstance(entries, list):
            raise InvalidMasterCvError(f"Section {title!r} must be a list of entries")
        for entry in entries:
            formatted = _format_entry(entry)
            if formatted:
                buckets[key].append(formatted)

    return CandidateSnapshot(
        contact=contact,
        education=buckets["education"],
        experience=buckets["experience"],
        projects=buckets["projects"],
        skills_tools=buckets["skills_tools"],
    )


def _format_contact(cv: dict[str, Any]) -> str | None:
    parts: list[str] = []
    name = cv.get("name")
    if isinstance(name, str) and name.strip():
        parts.append(name.strip())
    for field in ("email", "phone", "location", "website"):
        value = cv.get(field)
        if isinstance(value, list):
            for item in value:
                if item is not None and str(item).strip():
                    parts.append(str(item).strip())
        elif value is not None and str(value).strip():
            parts.append(str(value).strip())
    social = cv.get("social_networks")
    if isinstance(social, list):
        for item in social:
            if not isinstance(item, dict):
                continue
            network = item.get("network")
            username = item.get("username")
            if network and username:
                parts.append(f"{network}: {username}")
    return ", ".join(parts) if parts else None


def _format_entry(entry: Any) -> str:
    if isinstance(entry, str):
        return entry.strip()
    if not isinstance(entry, dict):
        return str(entry).strip()

    if "label" in entry and "details" in entry:
        label = _scalar(entry.get("label"))
        details = _scalar(entry.get("details"))
        if label and details:
            return f"{label}: {details}"
        return details or label

    if "institution" in entry or "area" in entry or "degree" in entry:
        bits = [
            _scalar(entry.get("degree")),
            _scalar(entry.get("area")),
            _scalar(entry.get("institution")),
            _date_bit(entry),
        ]
        head = ", ".join(bit for bit in bits if bit)
        return _with_highlights(head, entry)

    if "company" in entry or "position" in entry:
        position = _scalar(entry.get("position"))
        company = _scalar(entry.get("company"))
        if position and company:
            head = f"{position} at {company}"
        else:
            head = position or company
        date_bit = _date_bit(entry)
        if head and date_bit:
            head = f"{head} ({date_bit})"
        return _with_highlights(head, entry)

    if "name" in entry:
        name = _scalar(entry.get("name"))
        summary = _scalar(entry.get("summary"))
        if name and summary:
            head = f"{name}: {summary}"
        else:
            head = name or summary
        return _with_highlights(head, entry)

    if "bullet" in entry:
        return _scalar(entry.get("bullet"))
    if "number" in entry:
        return _scalar(entry.get("number"))
    if "reversed_number" in entry:
        return _scalar(entry.get("reversed_number"))

    # Fallback: preserve field values as written without inventing structure.
    pieces: list[str] = []
    for key, value in entry.items():
        if key == "highlights" and isinstance(value, list):
            continue
        text = _scalar(value)
        if text:
            pieces.append(f"{key}: {text}")
    head = "; ".join(pieces)
    return _with_highlights(head, entry)


def _with_highlights(head: str, entry: dict[str, Any]) -> str:
    highlights = entry.get("highlights")
    lines = [head] if head else []
    if isinstance(highlights, list):
        for item in highlights:
            text = _scalar(item)
            if text:
                lines.append(f"- {text}")
    return "\n".join(lines).strip()


def _date_bit(entry: dict[str, Any]) -> str:
    date = _scalar(entry.get("date"))
    if date:
        return date
    start = _scalar(entry.get("start_date"))
    end = _scalar(entry.get("end_date"))
    if start and end:
        return f"{start}–{end}"
    return end or start


def _scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(_scalar(item) for item in value if _scalar(item))
    text = str(value).strip()
    return text
