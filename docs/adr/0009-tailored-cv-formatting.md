# Tailored CV formatting

How the LLM tailor reshapes a Master CV into a Tailored CV for one Job Posting. Bound by [0003-no-fabricated-cv-content.md](0003-no-fabricated-cv-content.md) and [0007-rendercv-yaml-master-cv.md](0007-rendercv-yaml-master-cv.md). Edit Summary disclosure rules: [0012-edit-summary-rules.md](0012-edit-summary-rules.md). “First half of the page” means earlier in RenderCV YAML order (higher on the PDF after render) — not pixel or page-coordinate editing.

**Status:** accepted

## Operation priority

1. **Reorder** (primary) — move JD-relevant sections, entries, and bullets earlier.
2. **Emphasize / rephrase** — within an entry, lead with JD-aligned bullets; reword only from real content.
3. **Omit** lightly — prefer reorder over dropping whole jobs; disclose every omission in the Edit Summary.
4. **Summary** — rewrite only if a summary section already exists on the Master CV.

## What drives “more related”

Reorder ranking comes from the Job Posting’s required skills/duties and existing Relevance Evidence — not from Preference. Preference may influence whether the user Prepares; it must not reshape the CV to claim desire-fit the CV does not evidence.

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

Pinned sections keep their relative ranks; the tailor may place only **unpinned** sections freely (after pinned ones, in relative order). If `pinned_section_order` is absent or empty, the tailor may decide full section order. Invalid section names are ignored with a note in the Edit Summary. **v1 non-goal:** no pinning of individual entries or bullets; revisit only if section pins prove insufficient in real Prepares.

## Omission

- Prefer reorder and bullet reordering over omitting whole entries.
- Omit a bullet when it is clearly off-JD and keeps stronger Evidence lower.
- Omit a whole entry only when clearly irrelevant and timeline honesty is preserved (if needed, keep a minimal title/dates/employer entry and drop only off-topic bullets).
- Never omit to hide Weak Relevance; unmet requirements stay in the Gap Report.
- Every omission appears in the Edit Summary.

## Rephrase / emphasize

- May mirror JD vocabulary only when the Master CV already supports that meaning.
- Must not add tools, metrics, seniority, or outcomes absent from the Master CV.
- Must not keyword-stuff. Summary rewrite (if present): same rules; short, existing themes only.
