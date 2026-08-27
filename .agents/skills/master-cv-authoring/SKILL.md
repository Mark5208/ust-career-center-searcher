---
name: master-cv-authoring
description: Classify a Master CV Authoring Slice and hint which leaf to type.
disable-model-invocation: true
---

This invoke is the index when the user is unsure or wants both. Direct `/master-cv-content-interview` or `/master-cv-design-pins` is a valid Sitting on that surface alone.

The [Authoring write protocol](../master-cv-write-protocol.md) is not a skill. Do not invoke it as `/master-cv-write`. The router never runs it and never writes. The last named leaf runs it.

Rules: ADR-0018. Not a Master CV Enrichment session (ADR-0017). No fabricated experience (ADR-0003).

## 1. Open the Sitting

If this conversation already has an Authoring `/name`, continue that Sitting. Otherwise this invoke opens one. The Sitting continues until abort or one Authoring write protocol confirm. Several Slices may accumulate into one draft. Authoring is a Sitting, not a session. The draft is this conversation; there is no Sitting store. A new conversation is a new Sitting and does not inherit the prior draft.

The user's first speech nominates the Slice — including whatever they already said on invoke.

Done when this invoke has opened or continued the Sitting, or the user has aborted.

## 2. Classify the Slice

Classify only. Hint the leaf `/name`(s). The user types them. Do not start `/master-cv-content-interview` or `/master-cv-design-pins` from here.

- `cv` facts → `/master-cv-content-interview`
- Theme, knobs, locale, selected settings, or pins → `/master-cv-design-pins`
- A Slice with both → name both

Empty or vague → one question: content, design/pins, or both — then hint the leaf `/name`(s).

New section titles stay unpinned. Do not ask to pin them.

No gap-fill. No Master CV audit. Stay on Authoring classify-and-hint, not Enrichment and not Prepare.

Done when the user has been told which leaf `/name`(s) to type, or the one question has been asked.

## 3. Wait for the named leaf

A mixed ask is one Sitting: classify, tell the user to type the named leaves, combined draft, one Authoring write protocol confirm. The last named leaf runs the protocol once when every named piece is filled or dropped. Earlier leaves defer confirm.

A single-surface ask that arrived here still requires the user to type that leaf.

Apply every rule under Misfires.

Done when the user has typed the named leaf `/name`(s), dropped remaining named pieces, or the Sitting has stopped with no write.

## Misfires

Hinted leaf never typed: re-ask once to type the leaf. If they still do not, stop. Empty draft → no write.

Confirm while named pieces remain: remind the user to type the other leaf, or drop that piece. Then the last remaining leaf runs the Authoring write protocol.

Wrong leaf: one line that that piece belongs in the other `/name`. Do not start it from here. If they type it before confirm, mixed-Sitting path. If not, drop the piece; empty remainder → no write.
