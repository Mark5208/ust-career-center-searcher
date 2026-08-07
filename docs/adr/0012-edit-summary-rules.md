# Edit Summary rules

How the Edit Summary is produced at Prepare so the user can audit Master CV → Tailored CV changes before applying. Bound by [0003-no-fabricated-cv-content.md](0003-no-fabricated-cv-content.md), Tailored CV formatting in [0009-tailored-cv-formatting.md](0009-tailored-cv-formatting.md), and Gap Report rules in [0011-gap-report-rules.md](0011-gap-report-rules.md).

**Status:** accepted

## Role in the Preparation Packet

Edit Summary is a **first-class peer** of Gap Report and Tailored CV — not a footnote under the PDF. After Prepare, the intended review order is: Gap Report (what’s missing) → Edit Summary (what changed) → Tailored CV / PDF. Match Assessment remains the pre-Prepare fit view and may appear in the packet for context.

## Author

The same Prepare-pass tailor LLM produces the Edit Summary together with the Tailored CV (checklist-constrained). It is **not** a separate deterministic YAML diff engine. Completeness is **best-effort**: Prepare does not fail when disclosures look incomplete, and there is no second-pass structural validator that compares YAML trees to the summary.

## Required disclosures

Always list:

- Every **omission** (bullet or whole entry) — exhaustive; never truncated
- Every **section reorder**
- Every **cross-role chronology** break (JD-relevance order beating reverse-chronological across roles)
- Every **summary rewrite** (only when a summary section already existed)
- Every **invalid** `assistant.pinned_section_order` section name
- Every **material rephrase** (wording that shifts meaning, e.g. mirroring JD vocabulary)

Do **not** require a line for routine intra-entry bullet shuffles or light rephrases that do not shift meaning.

## Shape and labels

A short **grouped bullet list**. Fixed group headings appear only when that group has items:

- Omissions
- Section order
- Cross-role chronology
- Summary rewrite
- Pin notes
- Material rephrases

Omit empty groups. If nothing material changed: one line, “No material edits.”

Labels use human terms (section / employer / role / bullet gist) — not YAML paths or a unified diff.

**Material rephrase** bullets: one short line of **where** + gist of **before → after** (a few words each). Example: `Acme / Intern — “built internal tools” → “built Python data tooling”`. Omission and order bullets name the change only (no before/after prose).

## Length

No overall bullet cap. Omissions stay exhaustive. Other groups stay short by construction. A huge Edit Summary is a signal the tailor omitted too aggressively — fix the tailor, do not truncate the audit trail.

## Boundary with Gap Report

Strict separation. Edit Summary describes only Master → Tailored **edits**. It never lists JD gaps, Suggestions, or “you still need…”. If content was omitted, say what was dropped from the CV — not why the JD wants something else. Unmet requirements stay in the Gap Report.
