---
name: master-cv-content-interview
description: Gap-fill a user-nominated Slice of Master CV content, then write on confirm.
disable-model-invocation: true
---

Direct invoke is a valid Sitting on the `cv` surface alone. In a conversation that already has an Authoring `/name`, this invoke continues that Sitting.

The [Authoring write protocol](../master-cv-write-protocol.md) is not a skill. Do not invoke it as `/master-cv-write`.

Rules: ADR-0018. Not a Master CV Enrichment session (ADR-0017). No fabricated experience (ADR-0003).

## 1. Open the Sitting

If this conversation already has an Authoring `/name`, continue that Sitting. Otherwise this invoke opens one. Continue until abort or one Authoring write protocol confirm. Several Slices may accumulate into one draft. Authoring is a Sitting, not a session.

The user's first speech nominates the Slice — intent or dump, including whatever they already said on invoke. Wait for that speech. Do not open with a whole-Master-CV gap audit. If they paste a Job Posting or Gap Report, apply Job-agnostic.

Done when the Sitting has a user-nominated Slice, or the user has aborted.

## 2. Gap-fill the Slice

Typed slice-and-gap-fill of `cv` — not Enrichment's five dimensions, one entry, or one-follow-up cap. Ask only what this write still lacks: RenderCV required identity, plus user-affirmed prose for anything added or rewritten. Uncapped follow-ups, stay inside the Slice. If the dump already fills the Slice, skip further questions and go to the Authoring write protocol; its change list is the draft.

Stop when the Slice is filled, not when the Master CV is complete. The user may end the Slice; remaining gaps drop.

Apply every rule under Surface, Placement, Refuse, and Job-agnostic.

Done when every piece in the Slice is filled, dropped, or the user has ended the Slice.

## 3. Run the Authoring write protocol

If named `/master-cv-design-pins` pieces remain, defer confirm: ask the user to type that leaf or drop that piece.

Otherwise read [Authoring write protocol](../master-cv-write-protocol.md) and run it. Direct content-only Sitting: this leaf runs it. Mixed Sitting: this leaf runs it when it is the last named leaf and every named piece is filled or dropped. Keep the Sitting draft as accumulated, including any design-pins pieces.

Done when the protocol has finished, confirm is deferred to the other leaf, or the Sitting has stopped with no write.

## Surface

This leaf's interview mutates `cv` only: header, any section title, any of RenderCV's nine entry types. Add, modify, or remove highlights, entries, whole sections, and header fields, including identity on existing entries, when the user affirms it. In-section entry reorder when asked. Whole-section order is pins — leave it to `/master-cv-design-pins`.

Do not edit `design`, `locale`, `settings`, or `assistant.pinned_section_order` here. Preserve comments. Pin edits belong to `/master-cv-design-pins`; the protocol says when pins may change.

Experience, projects, and education may be deepened here; that overlap with Master CV Enrichment is allowed. Continue in this Sitting. Do not bounce to Enrichment.

A design, locale, settings, or pins ask: one line that it belongs in `/master-cv-design-pins`. Do not start that skill from here.

## Placement

Propose a section or entry only for pieces in this Slice that are unplaced or ambiguous, as soon as the entry type is needed for required fields. Offer an existing entry, or a new title plus one RenderCV type; the user may rename. Already-placed pieces skip placement.

One type per section. On clash, propose a different section or a new title.

New titles only when the user names them or confirms a proposal. They stay unpinned; do not ask to pin them. Snapshot-blind warning is the protocol's.

Stay inside the Slice. Do not recap the Sitting. Do not re-home entries outside the Slice.

## Refuse

Write only user-affirmed facts. "Make something up," "probably," and copying a fact onto a different entry without a new affirmation: do not write, and do not offer to invent for the user to edit. User-affirmed facts are writeable; there is no biography police.

A thin answer to a gap-fill question does not fill that gap and does not overwrite a real bullet. If the user nominated those exact generic words as the write, write them; do not punch up.

Identity-only new job, project, or school: ask once for a highlight; if none, still write identity. A publication with title and authors and no DOI is writeable. Deletes, reorders, header edits, and meaning-preserving rewrites are not a thinness problem. Meaning-preserving rewrite when asked: no new skills, tools, metrics, seniority, or outcomes the user did not affirm.

One bad piece: re-ask inside the Slice, then drop that piece; the rest continues in this Sitting.

## Job-agnostic

This skill records job-agnostic facts. A pasted Job Posting or Gap Report is not a question agenda. Keep any fact already stated. Say that the skill only records job-agnostic facts.
