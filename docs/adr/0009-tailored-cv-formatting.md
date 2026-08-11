# Tailored CV formatting

How the LLM tailor reshapes a Master CV into a Tailored CV for one Job Posting. Bound by [0003-no-fabricated-cv-content.md](0003-no-fabricated-cv-content.md) and [0007-rendercv-yaml-master-cv.md](0007-rendercv-yaml-master-cv.md). Edit Summary disclosure rules: [0012-edit-summary-rules.md](0012-edit-summary-rules.md). Master CV as full dossier / Enrichment: [0017-master-cv-enrichment.md](0017-master-cv-enrichment.md). “First half of the page” means earlier in RenderCV YAML order (higher on the PDF after render) — not pixel or page-coordinate editing.

**Status:** accepted

## Operation priority

1. **Reorder and select/omit** (primary) — move JD-relevant sections, entries, and bullets earlier; from a rich dossier Master, select apply-sized content by omitting off-JD bullets (and whole entries only when clearly irrelevant), disclosed in the Edit Summary.
2. **Emphasize / rephrase** — within an entry, lead with JD-aligned bullets; reword only from real content.
3. **Summary** — rewrite only if a summary section already exists on the Master CV.

## What drives “more related”

Reorder and selection ranking comes from the Job Posting’s required skills/duties and existing Relevance Evidence — not from Preference. Preference may influence whether the user Prepares; it must not reshape the CV to claim desire-fit the CV does not evidence.

Within one employer/role, keep date honesty (do not scramble chronology inside a job). Across roles, JD-relevance order may beat reverse-chronological when that surfaces stronger Evidence sooner; the Edit Summary must call out that reorder.

## Sections and entries

- Reorder **entries and bullets** aggressively for JD fit.
- Reorder **whole sections** when that clearly surfaces stronger Evidence earlier; do not invent new section types; never drop Contact / identity fields.
- Optional Master CV metadata the tailor honors and RenderCV must not show on the PDF:

```yaml
assistant:
  pinned_section_order:
    - education
    - experience
```

Pinned sections keep their relative ranks; the tailor may place only **unpinned** sections freely (after pinned ones, in relative order). If `pinned_section_order` is absent or empty, the tailor may decide full section order. Invalid section names are ignored with a note in the Edit Summary. **Parked:** no pinning of individual entries or bullets; revisit only if section pins prove insufficient in real Prepares (parking lot theme, separate from Master CV Enrichment).

## Omission / selection

- From a rich dossier Master, **selection/omission is a primary operation** alongside reorder so the Tailored CV stays apply-sized.
- Prefer dropping off-JD bullets inside a kept entry over keyword-stuffing or inventing.
- Omit a whole entry only when clearly irrelevant and timeline honesty is preserved (if needed, keep a minimal title/dates/employer entry and drop only off-topic bullets).
- Never omit to hide Weak Relevance; unmet requirements stay in the Gap Report.
- Every omission appears in the Edit Summary.

## Rephrase / emphasize

- May mirror JD vocabulary only when the Master CV already supports that meaning.
- Must not add tools, metrics, seniority, or outcomes absent from the Master CV.
- Must not keyword-stuff. Summary rewrite (if present): same rules; short, existing themes only.

## Considered Options

- **Omit lightly (prior rule)** — prefer reorder over dropping content; suited to short Masters before Enrichment. Retained for future revisit once real Enrichment depth and Prepare volume show whether aggressive select-from-dossier over-omits. Not the current primary rule.
