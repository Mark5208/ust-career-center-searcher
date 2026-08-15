# Master CV Enrichment

Standalone user-started flow to deepen Master CV content so the dossier holds holistic facts the user forgot to write (e.g. leadership and domain context beside tech). Bound by [0003-no-fabricated-cv-content.md](0003-no-fabricated-cv-content.md) and [0007-rendercv-yaml-master-cv.md](0007-rendercv-yaml-master-cv.md). Apply-sized selection from a rich Master: [0009-tailored-cv-formatting.md](0009-tailored-cv-formatting.md). Master CV change freshness: [0014-assessment-freshness-and-change-detection.md](0014-assessment-freshness-and-change-detection.md). LLM runtime: [0015-llm-runtime-for-v1.md](0015-llm-runtime-for-v1.md).

**Status:** accepted

## Decision

Master CV Enrichment is a **job-agnostic** dedicated UI (linked from Candidate files; Snapshot remains the inspect surface — no YAML editor or Master PDF viewer required here).

1. **Freeform start** — user describes an experience; not gated on picking from an enrichable-entry list.
2. **Placement confirm** — LLM suggests an existing entry or a **new entry under an existing section** (experience/projects; education if appropriate; skills lists stay hand-edited). User must confirm placement. New entries require user-confirmed identity (employer/title/dates or project name/dates). No new section types. LLM must not silently place or invent structure.
3. **Dimension steps** — short step flow for fixed dimensions: problem/context; technical work; collaboration/leadership; domain/impact; outcomes/metrics — skip empty; at most one clarifying follow-up per dimension. Not an open-ended chat.
4. **Highlights confirm** — tool drafts an **editable full highlights list** (kept existing + new); on explicit confirm, write ordinary entry content into the user’s Master CV path.
5. **Write rules** — Prepare/tailor never write the Master CV. Confirm write patches **only** the target entry (highlights; identity fields if new), atomically (temp → replace). Fingerprint the Master CV at session start; if it changed before confirm, **refuse** the write and require restart. One Enrichment session = one placement = one write. Session state is ephemeral (no durable resume across restarts).
6. **LLM** — separate **`LlmCvEnricher`** port on the same OpenAI-compatible env client/model as judge/tailor. LLM Unavailable blocks Enrichment LLM steps with a short non-secret reason and keeps ephemeral answers for retry; no heuristic/local draft. Fake enricher is tests-only. User-confirmed answers only — the LLM must not invent employers, dates, titles, skills, or outcomes the user did not affirm.
7. **Not Authoring** — Master CV Enrichment is not Master CV Authoring (skills, Sitting, Authoring write protocol). This ADR does not govern that family ([0018-master-cv-authoring.md](0018-master-cv-authoring.md)).

Not inside Prepare or Crawl; never silent mid-Prepare enrich.
