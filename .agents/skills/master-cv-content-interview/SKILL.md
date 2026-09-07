---
name: master-cv-content-interview
description: Interview a Holistic Slice or Detailed Slice of Master CV content, then write on confirm.
disable-model-invocation: true
---

Direct invoke is a valid Sitting on the `cv` surface alone. In a conversation that already has an Authoring `/name`, this invoke continues that Sitting.

The [Authoring write protocol](../master-cv-write-protocol.md) is not a skill. Do not invoke it as `/master-cv-write`.

Rules: ADR-0018. Not a Master CV Enrichment session (ADR-0017). No fabricated experience (ADR-0003).

## 1. Open the Sitting

If this conversation already has an Authoring `/name`, continue that Sitting. Otherwise this invoke opens one. Continue until abort or one Authoring write protocol confirm. Several Slices may accumulate into one draft. Authoring is a Sitting, not a session.

The user's first speech nominates the Slice — intent or dump, including whatever they already said on invoke. Wait for that speech. Stay inside that speech; there is no opening audit of the Master CV. If they paste a Job Posting or Gap Report, apply Job-agnostic.

Done when the Sitting has a user-nominated Slice, or the user has aborted.

## 2. Classify the Slice kind

Classify from that speech after they typed this leaf. The router does not hint kind.

Say one line naming kind and target (and the Slice list when there are several), then proceed unless they contradict. That line is the tell, not a recap and not a wait-for-yes.

- **Holistic Slice** — one experience, projects, or education entry, and they asked to deepen, complete, or cover it, or dumped that one entry without naming holes. A new or unplaced row named only by identity (company and position, institution and area, or project name, with dates if given) is covering that entry: take identity inside this Holistic Slice.
- **Detailed Slice** — named holes, other `cv` (header, skills/tools, several entries, delete, reorder), or a one-bullet edit. This kind does not walk Facets.
- Ambiguous ("Update X" with no further intent) → one question: walk the Facets, or named holes?
- Mixed speech → several Slices, not one hybrid ritual. A named hole plus a deepen on the same entry → two Slices. Header, skills/tools, or a different entry is always another Slice.
- Several Slices from one speech run in mention order. If mention order is unclear, one question which Slice first.
- Vague "deepen my experience" with no which-entry → one Placement question (existing or new).
- "Deepen all" → one question which experience, projects, or education entries this Sitting (identity list only). Each chosen entry is its own Holistic Slice.
- Kind does not convert in place. "Actually walk the five" nominates a new Holistic Slice; already-affirmed draft pieces stay. "Just write what we have" during a Holistic Slice skips remaining Facets.

Apply every rule under Surface and Placement.

Done when the Sitting has a classified Slice or Slice list, or the one question has been asked.

## 3. Interview the Slice

Interview the current Slice. When several remain, finish one, then tell-and-interview the next.

**Holistic Slice.** Apply every rule under Holistic Slice. Overlapping Enrichment-shaped deepen is this Holistic Slice.

**Detailed Slice.** Ask only what this write still lacks: RenderCV required identity, plus user-affirmed prose for anything added or rewritten. Uncapped follow-ups, stay inside the Slice. If the dump already fills the Slice, skip further questions.

Stop when the current Slice is filled, not when the Master CV is complete. The user may end the Slice; remaining gaps drop.

Apply every rule under Surface, Placement, Refuse, and Job-agnostic.

Done when every content Slice is filled, dropped, or ended.

## 4. Run the Authoring write protocol

If named `/master-cv-design-pins` pieces remain, defer confirm: ask the user to type that leaf or drop that piece.

Otherwise read [Authoring write protocol](../master-cv-write-protocol.md) and run it. Direct content-only Sitting: this leaf runs it. Mixed Sitting: this leaf runs it when it is the last named leaf and every named piece is filled or dropped. Keep the Sitting draft as accumulated, including any design-pins pieces.

Done when the protocol has finished, confirm is deferred to the other leaf, or the Sitting has stopped with no write.

## Surface

This leaf's interview mutates `cv` only: header, any section title, any of RenderCV's nine entry types. Add, modify, or remove highlights, entries, whole sections, and header fields, including identity on existing entries, when the user affirms it. In-section entry reorder when asked. Whole-section order is pins — leave it to `/master-cv-design-pins`.

Do not edit `design`, `locale`, `settings`, or `assistant.pinned_section_order` here. Preserve comments. Pin edits belong to `/master-cv-design-pins`; the protocol says when pins may change.

Experience, projects, and education may be a Holistic Slice here; that overlap with Master CV Enrichment is a Holistic Slice on this leaf. Continue here. Do not bounce to Enrichment or `/candidate/enrichment`. A design, locale, settings, or pins ask: one line that it belongs in `/master-cv-design-pins`. Do not start that skill from here.

## Placement

Propose a section or entry only for pieces in this Slice that are unplaced or ambiguous, as soon as the entry type is needed for required fields. Offer an existing entry, or a new title plus one RenderCV type; the user may rename. Already-placed pieces skip placement.

One type per section. On clash, propose a different section or a new title.

New titles only when the user names them or confirms a proposal. They stay unpinned; do not ask to pin them. Snapshot-blind warning is the protocol's.

Stay inside the Slice. Do not recap the Sitting. Do not re-home entries outside the Slice.

## Holistic Slice

Offer all five Facets in this order, one at a time: problem/context; technical work; collaboration/leadership; domain/impact; outcomes/metrics. They are interview coverage, not RenderCV keys. Extra keys are not a content schema. Prose lands in optional `summary` plus ordinary `highlights`.

Skip a Facet the dump already filled. Offer only remaining empty Facets. If the dump fills all five, draft the full `highlights` list and go to the Authoring write protocol.

The user may skip an empty Facet. At most one clarifying follow-up per Facet. A thin answer does not fill that Facet, does not mint a highlight, and is not punched up.

Each new or replaced highlight is a Capability bullet: what they did, with what, to what effect. A skill or tool appears in a bullet only when they affirmed it. That name does not add a skills/tools row.

Existing entry, every Facet skipped: leave `highlights` untouched.
New entry, no highlights after the Facet walk: ask once for a highlight; identity-only is then writeable.
Existing Holistic Slice write: replace the full `highlights` list — keep bullets that remain true, plus new Capability bullets from filled Facets.

Write or replace `summary` only when they affirm a role one-liner. Leave an existing `summary` untouched otherwise. A problem/context answer is not a `summary`.

Required identity for a new or unplaced entry, and identity facts in a deepen or dump about that row, stay inside this Holistic Slice.

## Refuse

Write only user-affirmed facts. "Make something up," "probably," and copying a fact onto a different entry without a new affirmation: do not write, and do not offer to invent for the user to edit. User-affirmed facts are writeable; there is no biography police.

A thin answer to a gap-fill question does not fill that gap and does not overwrite a real bullet. If the user nominated those exact generic words as the write, write them; do not punch up.

On a Detailed Slice, identity-only new job, project, or school: ask once for a highlight; if none, still write identity. A publication with title and authors and no DOI is writeable. Deletes, reorders, header edits, and meaning-preserving rewrites are not a thinness problem. Meaning-preserving rewrite when asked: no new skills, tools, metrics, seniority, or outcomes the user did not affirm.

One bad piece: re-ask inside the Slice, then drop that piece; the rest continues in this Sitting.

## Job-agnostic

This skill records job-agnostic facts. A pasted Job Posting or Gap Report is not a question agenda. Keep any fact already stated. Say that the skill only records job-agnostic facts.
