"""Live OpenAI-compatible LlmJudge / LlmCvTailor / LlmCvEnricher (ADR-0015 / 0017). Fake stays in tests only."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, NoReturn

import httpx

from job_finding_assistant.candidate_snapshot import CandidateSnapshot
from job_finding_assistant.enrichment import PlacementSuggestion
from job_finding_assistant.match_assessment import (
    ConstraintOutcome,
    EvidencePair,
    HardConstraintJudgment,
    PreferenceJudgment,
    RelevanceJudgment,
)
from job_finding_assistant.preparation_packet import (
    EditSummary,
    GapItem,
    GapReport,
    TailorResult,
)

DEFAULT_LLM_MODEL = "gpt-4.1-mini"
DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
_ENV_API_KEY = "JOB_FINDING_ASSISTANT_LLM_API_KEY"
_ENV_BASE_URL = "JOB_FINDING_ASSISTANT_LLM_BASE_URL"
_ENV_MODEL = "JOB_FINDING_ASSISTANT_LLM_MODEL"

_SECRET_FRAGMENT = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")


@dataclass(frozen=True)
class LlmRuntimeConfig:
    """Environment-only LLM credentials and model (no UI / disk secrets)."""

    api_key: str | None
    base_url: str = DEFAULT_LLM_BASE_URL
    model: str = DEFAULT_LLM_MODEL


def load_llm_runtime_config(
    environ: dict[str, str] | None = None,
) -> LlmRuntimeConfig:
    """Load LLM runtime settings from the process environment."""
    env = environ if environ is not None else os.environ
    raw_key = env.get(_ENV_API_KEY, "").strip()
    raw_base = env.get(_ENV_BASE_URL, "").strip()
    raw_model = env.get(_ENV_MODEL, "").strip()
    return LlmRuntimeConfig(
        api_key=raw_key or None,
        base_url=raw_base or DEFAULT_LLM_BASE_URL,
        model=raw_model or DEFAULT_LLM_MODEL,
    )


def _sanitize_reason(message: str) -> str:
    """Return a short non-secret reason; never echo API keys."""
    cleaned = _SECRET_FRAGMENT.sub("[redacted]", message).strip()
    if not cleaned:
        return "LLM Unavailable: provider error"
    if cleaned.lower().startswith("llm unavailable"):
        return cleaned
    return f"LLM Unavailable: {cleaned}"


class LlmUnavailableError(RuntimeError):
    """Live LLM call cannot complete; map to Pending / keep-prior or atomic Prepare fail."""

    def __init__(self, reason: str) -> None:
        self.reason = _sanitize_reason(reason)
        super().__init__(self.reason)


def _guard_unexpected(exc: BaseException, *, fallback: str) -> NoReturn:
    """Re-raise LlmUnavailableError; map anything else to a short safe reason."""
    if isinstance(exc, LlmUnavailableError):
        raise exc
    raise LlmUnavailableError(fallback) from exc


class UnavailableLlmJudge:
    """Normal-app placeholder when the API key is missing (never Fake)."""

    def __init__(self, reason: str = "LLM Unavailable: API key not configured") -> None:
        self._reason = _sanitize_reason(reason)

    def available(self) -> bool:
        return False

    def unavailable_reason(self) -> str:
        return self._reason

    def judge_hard_constraint(
        self,
        *,
        hard_constraints_text: str,
        job_detail_fields: dict[str, str],
    ) -> HardConstraintJudgment:
        del hard_constraints_text, job_detail_fields
        raise LlmUnavailableError(self._reason)

    def judge_preference(
        self,
        *,
        preferences_text: str,
        job_detail_fields: dict[str, str],
    ) -> PreferenceJudgment:
        del preferences_text, job_detail_fields
        raise LlmUnavailableError(self._reason)

    def judge_relevance(
        self,
        *,
        job_detail_fields: dict[str, str],
        candidate_snapshot: CandidateSnapshot,
    ) -> RelevanceJudgment:
        del job_detail_fields, candidate_snapshot
        raise LlmUnavailableError(self._reason)


class UnavailableLlmCvTailor:
    """Normal-app placeholder when the API key is missing (never Fake)."""

    def __init__(self, reason: str = "LLM Unavailable: API key not configured") -> None:
        self._reason = _sanitize_reason(reason)

    def available(self) -> bool:
        return False

    def unavailable_reason(self) -> str:
        return self._reason

    def tailor(
        self,
        *,
        master_cv_yaml: str,
        candidate_snapshot: CandidateSnapshot,
        job_detail_fields: dict[str, str],
        relevance_evidence: list[EvidencePair],
        hard_constraint_outcome: ConstraintOutcome,
        hard_constraint_reason: str,
        prior_attempt_errors: list[str] | None = None,
    ) -> TailorResult:
        del (
            master_cv_yaml,
            candidate_snapshot,
            job_detail_fields,
            relevance_evidence,
            hard_constraint_outcome,
            hard_constraint_reason,
            prior_attempt_errors,
        )
        raise LlmUnavailableError(self._reason)


class UnavailableLlmCvEnricher:
    """Normal-app placeholder when the API key is missing (never Fake)."""

    def __init__(self, reason: str = "LLM Unavailable: API key not configured") -> None:
        self._reason = _sanitize_reason(reason)

    def available(self) -> bool:
        return False

    def unavailable_reason(self) -> str:
        return self._reason

    def suggest_placement(
        self,
        *,
        freeform: str,
        master_cv_yaml: str,
    ) -> PlacementSuggestion:
        del freeform, master_cv_yaml
        raise LlmUnavailableError(self._reason)

    def clarifying_followup(
        self,
        *,
        dimension: str,
        answer: str,
        freeform: str,
    ) -> str | None:
        del dimension, answer, freeform
        raise LlmUnavailableError(self._reason)

    def draft_highlights(
        self,
        *,
        freeform: str,
        placement: PlacementSuggestion,
        dimension_answers: dict[str, str],
        existing_highlights: list[str],
    ) -> list[str]:
        del freeform, placement, dimension_answers, existing_highlights
        raise LlmUnavailableError(self._reason)


_HARD_CONSTRAINT_SYSTEM = """You are the Hard Constraint judge for a job-finding assistant.
Input isolation: you receive only the Hard Constraints file text and the Job Posting.
Never use Master CV, Candidate Snapshot, or Preferences. Non-negotiables are about the job.

For each applicable Hard Constraints line against the posting:
- Fail a line only on a clear contradiction with the posting.
- Unknown a line when the posting is silent or ambiguous and nothing clearly violates it.
- Pass a line only when it is clearly satisfied (or clearly N/A).

Overall outcome precedence:
1. Fail if any line fails.
2. Else unknown if any applicable line is unknown.
3. Else pass.

Unknown never counts as fail. Soft or hedged wording (“prefer not…”) does not belong here —
do not fail on soft wants. Bias under-fail rather than over-fail.
Clear contradiction → fail. Broader/vague geography or unstated location → unknown, not fail.
Soft JD language (“preferred”, “nice to have”) against a hard user ban → default unknown unless
the posting clearly still requires the banned thing.

Respond with JSON only:
{
  "outcome": "pass" | "fail" | "unknown",
  "reason": "short reason naming decisive Hard Constraints line(s) and posting fact (or not stated)",
  "evidence": [
    {"job_excerpt": "...", "candidate_excerpt": "Hard Constraints line or not stated", "role": "..."}
  ]
}
Evidence is optional light pairs (0–3). No CV excerpts.
"""

_PREFERENCE_SYSTEM = """You are the Preference judge for a job-finding assistant.
Input isolation: you receive only the Preferences file text and the Job Posting.
Never use Master CV or Candidate Snapshot.

Preference is desire (likes/avoids), not capability. Honor ordering or “higher / nice-to-have”
language when the user wrote a hierarchy.

- Strong: posting clearly fits most or all high-priority likes, and does not clearly match any
  explicit avoid/dislike.
- Mixed: partial fit — some likes match and some miss; likes match but an avoid is only
  mildly/softly present; or priorities conflict. If the posting is silent on a priority, treat
  that priority as unknown (not a miss); unknowns lean Mixed rather than Weak unless core likes
  clearly fail.
- Weak: posting mainly misses the likes, or clearly matches an explicit avoid — a clear avoid
  match caps Preference at Weak even when other likes fit (soft “prefer to avoid” may allow Mixed).

Respond with JSON only:
{
  "preference": "Strong" | "Mixed" | "Weak",
  "reason": "short reason citing which Preferences lines matched, missed, or were unknown",
  "evidence": [
    {"job_excerpt": "...", "candidate_excerpt": "Preferences line", "role": "..."}
  ]
}
No CV Evidence.
"""

_RELEVANCE_SYSTEM = """You are the Relevance judge for a job-finding assistant.
Input isolation: you receive only the Candidate Snapshot (and implied Master CV content in it)
and the Job Posting. Never use Preferences. Do not apply Hard Constraints inside Relevance.

Relevance is capability vs the JD. Required / must-have / minimum JD language first;
preferred / nice-to-have secondary. Evidence-backed only; never invent CV content.

- Strong: core required duties and must-have skills largely supported by concrete Snapshot/CV
  excerpts. Nice-to-haves may be partial.
- Mixed: some core requirements evidenced, others missing or only weakly related; or title/level
  roughly fits but several must-haves lack Evidence. Vague JD leans Mixed, not Strong.
- Weak: most core requirements lack Evidence, or the role’s core function clearly does not match
  experience on the CV.

Conservative adjacency: related/transferable experience may support Mixed, not Strong, and only
when Evidence names the adjacent thing honestly. Strong requires the core of the requirement as
written (or clearly equivalent tool in the same family and same seniority context with clear Evidence).

Respond with JSON only:
{
  "relevance": "Strong" | "Mixed" | "Weak",
  "evidence": [
    {
      "job_excerpt": "Job Posting excerpt",
      "candidate_excerpt": "Snapshot/CV excerpt or not found",
      "role": "supports Relevance | weakens Relevance | ..."
    }
  ]
}
Provide about three to seven Evidence pairs. The band must be consistent with that Evidence.
"""

_TAILOR_SYSTEM = """You prepare one Preparation Packet: Gap Report, Tailored CV (RenderCV YAML),
and Edit Summary. Never invent employers, dates, titles, skills, metrics, or outcomes absent
from the Master CV. Preferences are not inputs and must not drive capability claims.

Gap Report (build first conceptually):
- Inputs: Job Posting, Candidate Snapshot / Master CV, Relevance Evidence; include Hard Constraint
  failures when Hard Constraint failed. Do not use Preferences to invent gaps.
- Prefer required / must-have / minimum JD items; skip pure nice-to-haves by default.
- Omit fully evidenced requirements. Cap about 5–10 items.
- Status missing = no credible Master CV Evidence (“not found”); partial = related but incomplete.
- Suggestions are non-fictional guidance to the user — never license to add missing content to the CV.
- When Hard Constraint failed: include those failures with Suggestion along the lines of
  “only proceed if you accept this deal-breaker”.
- Empty Gap Report is valid when there are no required gaps.

Tailored CV formatting:
1. Reorder (primary) — move JD-relevant sections, entries, and bullets earlier in YAML order.
2. Emphasize / rephrase — within an entry, lead with JD-aligned bullets; reword only from real content.
3. Omit lightly — prefer reorder over dropping whole jobs; disclose every omission.
4. Summary — rewrite only if a summary section already exists on the Master CV.
- Reorder ranking from JD required skills/duties and Relevance Evidence — not Preference.
- Honor optional Master CV assistant.pinned_section_order: pinned sections keep relative ranks;
  place only unpinned sections freely after pinned ones. Invalid pin names → Edit Summary pin_notes.
- Preserve RenderCV YAML structure; never drop Contact / identity fields.
- Must not keyword-stuff or fill Missing gaps with invented content.

Edit Summary (Master → Tailored audit only; never JD gaps):
- Exhaustive omissions; every section reorder; every cross-role chronology break; every summary
  rewrite; every invalid pin; every material rephrase (where + before → after gist).
- Groups: omissions, section_order, cross_role_chronology, summary_rewrite, pin_notes,
  material_rephrases. Omit empty groups (empty arrays). If nothing material changed: put exactly
  one line “No material edits.” in omissions (other groups empty).

Respond with JSON only:
{
  "gap_report": {
    "items": [
      {
        "requirement": "...",
        "status": "missing" | "partial",
        "evidence": "Master CV Evidence or not found",
        "suggestion": "..."
      }
    ]
  },
  "edit_summary": {
    "omissions": ["..."],
    "section_order": ["..."],
    "cross_role_chronology": ["..."],
    "summary_rewrite": ["..."],
    "pin_notes": ["..."],
    "material_rephrases": ["..."]
  },
  "tailored_yaml": "full RenderCV YAML string"
}
"""


class OpenAiCompatibleLlmClient:
    """Thin OpenAI-compatible chat-completions client (one model for judge + tailor)."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_LLM_BASE_URL,
        model: str = DEFAULT_LLM_MODEL,
        http_client: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._owns_client = http_client is None
        self._timeout = timeout
        self._http = http_client or httpx.Client(timeout=timeout)

    @property
    def model(self) -> str:
        return self._model

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        """Call chat completions and parse a JSON object from the assistant message."""
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            response = self._http.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise LlmUnavailableError("provider timed out") from exc
        except httpx.HTTPError as exc:
            raise LlmUnavailableError("provider request failed") from exc

        if response.status_code >= 400:
            raise LlmUnavailableError(f"provider HTTP {response.status_code}")

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("assistant content must be a string")
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise TypeError("JSON response must be an object")
            return parsed
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as exc:
            raise LlmUnavailableError("invalid provider response") from exc


def _format_job_fields(job_detail_fields: dict[str, str]) -> str:
    lines = []
    for key, value in job_detail_fields.items():
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _format_snapshot(snapshot: CandidateSnapshot) -> str:
    parts = [
        f"contact: {snapshot.contact or ''}",
        "education:",
        *[f"- {item}" for item in snapshot.education],
        "experience:",
        *[f"- {item}" for item in snapshot.experience],
        "projects:",
        *[f"- {item}" for item in snapshot.projects],
        "skills_tools:",
        *[f"- {item}" for item in snapshot.skills_tools],
    ]
    return "\n".join(parts)


def _parse_evidence(raw: Any) -> list[EvidencePair]:
    if not isinstance(raw, list):
        return []
    pairs: list[EvidencePair] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        pairs.append(
            EvidencePair(
                job_excerpt=str(item.get("job_excerpt") or ""),
                candidate_excerpt=str(item.get("candidate_excerpt") or ""),
                role=str(item.get("role") or ""),
            )
        )
    return pairs


class OpenAiCompatibleLlmJudge:
    """Live LlmJudge with ADR-0008 / ADR-0010 rubrics in prompts and input isolation."""

    def __init__(self, client: OpenAiCompatibleLlmClient) -> None:
        self._client = client

    def available(self) -> bool:
        return True

    def unavailable_reason(self) -> str | None:
        return None

    def judge_hard_constraint(
        self,
        *,
        hard_constraints_text: str,
        job_detail_fields: dict[str, str],
    ) -> HardConstraintJudgment:
        try:
            user = (
                "Hard Constraints file:\n"
                f"{hard_constraints_text}\n\n"
                "Job Posting:\n"
                f"{_format_job_fields(job_detail_fields)}\n"
            )
            data = self._client.complete_json(system=_HARD_CONSTRAINT_SYSTEM, user=user)
            outcome = data.get("outcome")
            if outcome not in ("pass", "fail", "unknown"):
                raise LlmUnavailableError("invalid Hard Constraint outcome")
            reason = str(data.get("reason") or "").strip()
            if not reason:
                raise LlmUnavailableError("missing Hard Constraint reason")
            return HardConstraintJudgment(
                outcome=outcome,
                reason=reason,
                evidence=_parse_evidence(data.get("evidence")),
            )
        except Exception as exc:
            _guard_unexpected(exc, fallback="unexpected judge error")

    def judge_preference(
        self,
        *,
        preferences_text: str,
        job_detail_fields: dict[str, str],
    ) -> PreferenceJudgment:
        try:
            user = (
                "Preferences file:\n"
                f"{preferences_text}\n\n"
                "Job Posting:\n"
                f"{_format_job_fields(job_detail_fields)}\n"
            )
            data = self._client.complete_json(system=_PREFERENCE_SYSTEM, user=user)
            preference = data.get("preference")
            if preference not in ("Strong", "Mixed", "Weak"):
                raise LlmUnavailableError("invalid Preference band")
            reason = str(data.get("reason") or "").strip()
            if not reason:
                raise LlmUnavailableError("missing Preference reason")
            return PreferenceJudgment(
                preference=preference,
                reason=reason,
                evidence=_parse_evidence(data.get("evidence")),
            )
        except Exception as exc:
            _guard_unexpected(exc, fallback="unexpected judge error")

    def judge_relevance(
        self,
        *,
        job_detail_fields: dict[str, str],
        candidate_snapshot: CandidateSnapshot,
    ) -> RelevanceJudgment:
        try:
            user = (
                "Candidate Snapshot:\n"
                f"{_format_snapshot(candidate_snapshot)}\n\n"
                "Job Posting:\n"
                f"{_format_job_fields(job_detail_fields)}\n"
            )
            data = self._client.complete_json(system=_RELEVANCE_SYSTEM, user=user)
            relevance = data.get("relevance")
            if relevance not in ("Strong", "Mixed", "Weak"):
                raise LlmUnavailableError("invalid Relevance band")
            evidence = _parse_evidence(data.get("evidence"))
            if not evidence:
                raise LlmUnavailableError("missing Relevance Evidence")
            return RelevanceJudgment(relevance=relevance, evidence=evidence)
        except Exception as exc:
            _guard_unexpected(exc, fallback="unexpected judge error")


class OpenAiCompatibleLlmCvTailor:
    """Live LlmCvTailor with ADR-0009 / 0011 / 0012 rubrics; same model as the judge."""

    def __init__(self, client: OpenAiCompatibleLlmClient) -> None:
        self._client = client

    def available(self) -> bool:
        return True

    def unavailable_reason(self) -> str | None:
        return None

    def tailor(
        self,
        *,
        master_cv_yaml: str,
        candidate_snapshot: CandidateSnapshot,
        job_detail_fields: dict[str, str],
        relevance_evidence: list[EvidencePair],
        hard_constraint_outcome: ConstraintOutcome,
        hard_constraint_reason: str,
        prior_attempt_errors: list[str] | None = None,
    ) -> TailorResult:
        try:
            evidence_lines = [
                f"- job: {pair.job_excerpt} | candidate: {pair.candidate_excerpt} | role: {pair.role}"
                for pair in relevance_evidence
            ]
            retry_note = ""
            if prior_attempt_errors:
                errors_block = "\n".join(f"- {error}" for error in prior_attempt_errors)
                retry_note = (
                    "\nYour previous Tailored YAML failed RenderCV's schema with these "
                    f"problems:\n{errors_block}\n"
                    "Return a corrected full Gap Report, Edit Summary, and Tailored YAML "
                    "together that fixes them — not a partial patch.\n"
                )
            user = (
                "Master CV YAML:\n"
                f"{master_cv_yaml}\n\n"
                "Candidate Snapshot:\n"
                f"{_format_snapshot(candidate_snapshot)}\n\n"
                "Job Posting:\n"
                f"{_format_job_fields(job_detail_fields)}\n\n"
                "Relevance Evidence:\n"
                f"{chr(10).join(evidence_lines) if evidence_lines else '(none)'}\n\n"
                f"Hard Constraint outcome: {hard_constraint_outcome}\n"
                f"Hard Constraint reason: {hard_constraint_reason}\n"
                f"{retry_note}"
            )
            data = self._client.complete_json(system=_TAILOR_SYSTEM, user=user)
            tailored_yaml = data.get("tailored_yaml")
            if not isinstance(tailored_yaml, str) or not tailored_yaml.strip():
                raise LlmUnavailableError("missing Tailored YAML")
            return TailorResult(
                gap_report=_parse_gap_report(data.get("gap_report")),
                edit_summary=_parse_edit_summary(data.get("edit_summary")),
                tailored_yaml=tailored_yaml,
            )
        except Exception as exc:
            _guard_unexpected(exc, fallback="unexpected tailor error")


_ENRICH_PLACEMENT_SYSTEM = """You suggest Master CV Enrichment placement for a job-finding assistant.
Return JSON only:
{
  "section": "experience" | "projects" | "education",
  "mode": "existing" | "new",
  "entry_index": integer or null,
  "company": string or null,
  "position": string or null,
  "name": string or null,
  "start_date": string or null,
  "end_date": string or null,
  "label": short human label
}
Rules: suggest an existing entry when the freeform clearly matches one; otherwise new under an existing section type (experience/projects/education). Never invent section types. Skills lists are hand-edited — do not place there. entry_index is 0-based within that section list for existing mode.
"""

_ENRICH_FOLLOWUP_SYSTEM = """You may ask at most one short clarifying follow-up for one Enrichment dimension.
Return JSON: {"followup": string or null}. Use null when the answer is already clear. Do not invent facts.
"""

_ENRICH_HIGHLIGHTS_SYSTEM = """You draft an editable full highlights list for one Master CV entry.
Return JSON: {"highlights": ["...", ...]}.
Keep existing highlights that remain true; add new bullets only from the user's freeform and dimension answers. Never invent employers, dates, titles, skills, or outcomes the user did not affirm.
"""


class OpenAiCompatibleLlmCvEnricher:
    """Live LlmCvEnricher on the same OpenAI-compatible client/model as judge/tailor."""

    def __init__(self, client: OpenAiCompatibleLlmClient) -> None:
        self._client = client

    def available(self) -> bool:
        return True

    def unavailable_reason(self) -> str | None:
        return None

    def suggest_placement(
        self,
        *,
        freeform: str,
        master_cv_yaml: str,
    ) -> PlacementSuggestion:
        try:
            user = (
                f"Freeform experience:\n{freeform}\n\n"
                f"Master CV YAML:\n{master_cv_yaml}\n"
            )
            data = self._client.complete_json(
                system=_ENRICH_PLACEMENT_SYSTEM, user=user
            )
            section = data.get("section")
            mode = data.get("mode")
            if section not in ("experience", "projects", "education"):
                raise LlmUnavailableError("invalid Enrichment section")
            if mode not in ("existing", "new"):
                raise LlmUnavailableError("invalid Enrichment placement mode")
            entry_index = data.get("entry_index")
            if mode == "existing":
                if not isinstance(entry_index, int) or entry_index < 0:
                    raise LlmUnavailableError("invalid Enrichment entry_index")
            else:
                entry_index = None
            return PlacementSuggestion(
                section=section,
                mode=mode,
                entry_index=entry_index,
                company=_optional_str(data.get("company")),
                position=_optional_str(data.get("position")),
                name=_optional_str(data.get("name")),
                start_date=_optional_str(data.get("start_date")),
                end_date=_optional_str(data.get("end_date")),
                label=_optional_str(data.get("label")) or "",
            )
        except Exception as exc:
            _guard_unexpected(exc, fallback="unexpected enricher error")

    def clarifying_followup(
        self,
        *,
        dimension: str,
        answer: str,
        freeform: str,
    ) -> str | None:
        try:
            user = (
                f"Dimension: {dimension}\n"
                f"Answer: {answer}\n"
                f"Freeform: {freeform}\n"
            )
            data = self._client.complete_json(
                system=_ENRICH_FOLLOWUP_SYSTEM, user=user
            )
            followup = data.get("followup")
            if followup is None:
                return None
            text = str(followup).strip()
            return text or None
        except Exception as exc:
            _guard_unexpected(exc, fallback="unexpected enricher error")

    def draft_highlights(
        self,
        *,
        freeform: str,
        placement: PlacementSuggestion,
        dimension_answers: dict[str, str],
        existing_highlights: list[str],
    ) -> list[str]:
        try:
            answers = "\n".join(
                f"- {key}: {value}" for key, value in dimension_answers.items()
            )
            user = (
                f"Freeform:\n{freeform}\n\n"
                f"Placement: {placement.mode} {placement.section} "
                f"index={placement.entry_index} label={placement.label}\n\n"
                f"Existing highlights:\n"
                f"{chr(10).join(f'- {h}' for h in existing_highlights) or '(none)'}\n\n"
                f"Dimension answers:\n{answers or '(none)'}\n"
            )
            data = self._client.complete_json(
                system=_ENRICH_HIGHLIGHTS_SYSTEM, user=user
            )
            raw = data.get("highlights")
            if not isinstance(raw, list) or not raw:
                raise LlmUnavailableError("missing Enrichment highlights")
            highlights = [str(item).strip() for item in raw if str(item).strip()]
            if not highlights:
                raise LlmUnavailableError("missing Enrichment highlights")
            return highlights
        except Exception as exc:
            _guard_unexpected(exc, fallback="unexpected enricher error")


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_gap_report(raw: Any) -> GapReport:
    if not isinstance(raw, dict):
        return GapReport()
    items_raw = raw.get("items")
    if not isinstance(items_raw, list):
        return GapReport()
    items: list[GapItem] = []
    for item in items_raw:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        if status not in ("missing", "partial"):
            continue
        requirement = str(item.get("requirement") or "").strip()
        if not requirement:
            continue
        items.append(
            GapItem(
                requirement=requirement,
                status=status,
                evidence=str(item.get("evidence") or "not found"),
                suggestion=str(item.get("suggestion") or ""),
            )
        )
    return GapReport(items=tuple(items))


def _parse_edit_summary(raw: Any) -> EditSummary:
    if not isinstance(raw, dict):
        return EditSummary()

    def strings(key: str) -> tuple[str, ...]:
        value = raw.get(key)
        if not isinstance(value, list):
            return ()
        return tuple(str(entry) for entry in value if str(entry).strip())

    return EditSummary(
        omissions=strings("omissions"),
        section_order=strings("section_order"),
        cross_role_chronology=strings("cross_role_chronology"),
        summary_rewrite=strings("summary_rewrite"),
        pin_notes=strings("pin_notes"),
        material_rephrases=strings("material_rephrases"),
    )


def build_llm_ports(
    *,
    api_key: str | None = None,
    base_url: str = DEFAULT_LLM_BASE_URL,
    model: str = DEFAULT_LLM_MODEL,
    http_client: httpx.Client | None = None,
    config: LlmRuntimeConfig | None = None,
) -> tuple[
    OpenAiCompatibleLlmJudge | UnavailableLlmJudge,
    OpenAiCompatibleLlmCvTailor | UnavailableLlmCvTailor,
    OpenAiCompatibleLlmCvEnricher | UnavailableLlmCvEnricher,
]:
    """Build judge + tailor + enricher for the normal app path (never Fake)."""
    if config is not None:
        api_key = config.api_key
        base_url = config.base_url
        model = config.model
    if not api_key:
        reason = "LLM Unavailable: API key not configured"
        return (
            UnavailableLlmJudge(reason),
            UnavailableLlmCvTailor(reason),
            UnavailableLlmCvEnricher(reason),
        )
    client = OpenAiCompatibleLlmClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        http_client=http_client,
    )
    return (
        OpenAiCompatibleLlmJudge(client),
        OpenAiCompatibleLlmCvTailor(client),
        OpenAiCompatibleLlmCvEnricher(client),
    )
