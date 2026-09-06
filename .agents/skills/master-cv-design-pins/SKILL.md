---
name: master-cv-design-pins
description: Gap-fill a user-nominated Slice of Master CV design and pins, then write on confirm.
disable-model-invocation: true
---

Direct invoke is a valid Sitting on the design/pins surface alone. In a conversation that already has an Authoring `/name`, this invoke continues that Sitting.

The [Authoring write protocol](../master-cv-write-protocol.md) is not a skill. Do not invoke it as `/master-cv-write`.

Rules: ADR-0018. Not a Master CV Enrichment session (ADR-0017). No fabricated experience (ADR-0003).

## 1. Open the Sitting

If this conversation already has an Authoring `/name`, continue that Sitting. Otherwise this invoke opens one. Continue until abort or one Authoring write protocol confirm. Several Slices may accumulate into one draft. Authoring is a Sitting, not a session.

The user's first speech nominates the Slice — a named theme id, knob, locale, settings value, pin list, or a look without a theme id, including whatever they already said on invoke. Wait for that speech. Open on that nomination; do not audit theme, knobs, or pins.

A look without a theme id still needs an id: ask for a theme id. Listing the nine built-ins without picking one is a valid ask. Until they name a theme id, do not propose or write a theme or palette. Write knobs only when they name a concrete value.

If they paste a Job Posting or Gap Report, apply Job-agnostic.

Done when the Sitting has a user-nominated Slice, or the user has aborted.

## 2. Gap-fill the Slice

Named-write gap-fill of design, locale, selected settings, and pins. Ask only for a theme id, a concrete knob/locale/settings value, or a pin list of would-be `cv.sections` keys. Do not pick a theme, a measurement, or a pin order the user did not name. Uncapped follow-ups, stay inside the Slice. If the ask already fills the Slice, skip further questions and go to the Authoring write protocol; its change list is the draft.

This leaf does not walk Facets. A design-pins Slice is named-write of the nominated pieces only.

Stop when the Slice is filled, not when every knob is done. The user may end the Slice; remaining gaps drop. Empty remainder → no write. When the Slice is filled or dropped, go to the protocol or stop — no further layout questions, no offer of theme, knobs, or pins they did not name. A misfire bounce to `/master-cv-content-interview` is not an offer.

Apply every rule under Surface, Themes, Pins, Refuse, and Job-agnostic.

Done when every piece in the Slice is filled, dropped, or the user has ended the Slice.

## 3. Run the Authoring write protocol

If named `/master-cv-content-interview` pieces remain, defer confirm: ask the user to type that leaf or drop that piece.

Otherwise read [Authoring write protocol](../master-cv-write-protocol.md) and run it. Direct design/pins-only Sitting: this leaf runs it. Mixed Sitting: this leaf runs it when it is the last named leaf and every named piece is filled or dropped. Keep the Sitting draft as accumulated, including any content-interview pieces.

Done when the protocol has finished, confirm is deferred to the other leaf, or the Sitting has stopped with no write.

## Surface

This leaf's interview mutates `design`, `locale`, selected `settings`, and `assistant.pinned_section_order` only. Nested visual knobs: `page`, `colors`, `typography`, `links`, `header`, `section_titles`, `sections`, `entries`. Settings: `bold_keywords`, `pdf_title`, `current_date`. Stay inside keys the chosen theme's schema already defines.

Theme, knobs, locale, selected settings, and pins are each independently optional. Leave `design.theme` unset unless they name a theme id — RenderCV's render default is not a write. Empty or omitted pins are complete. A greenfield dossier may never invoke this leaf.

A `cv` edit ask: one line that it belongs in `/master-cv-content-interview`. Do not start that skill from here.

Section order is pins only. Leave `cv.sections` key order as it is. Preserve comments. Do not write `design.templates` or `settings.render_command`.

New section titles stay unpinned unless the user names them in this Slice. Do not prompt to pin a new title.

Continue in this Sitting for design and pins. Do not bounce to Enrichment.

## Themes

Any of the nine built-in themes. A custom local theme folder only if the file already names it, or the user asks and the folder is actually there. Do not invent a custom theme.

Theme switch: write the new `design.theme`. Drop other `design.*` knobs unless the user asked to keep a specific one. Leave `locale`, `settings`, and pins. The change list names what was dropped.

If the file has no `design.theme` and the user only names knobs, leave theme unset. Do not insert `theme: classic`.

The Authoring write protocol change list is the preview. Do not render a Master PDF.

## Pins

`assistant.pinned_section_order` only. Reorder; add a name only if it is a key on the Sitting would-be `cv.sections` at this gap-fill, including titles added earlier in this Sitting; unpin; clear (empty list or omit → tailor full freedom). A name not yet in that draft: re-ask once, then drop that piece. Do not add a `cv.sections` title to satisfy a pin. If this leaf runs first and `cv.sections` is empty, drop the pin piece; the Sitting continues. No other `assistant.*` keys. No entry or bullet pins.

## Refuse

Write only named design and pins. "Make something up," "probably," inventing a palette or theme for the user to edit: do not write.

A thin answer: re-ask once, then drop that piece — still no theme id, no concrete value, no pin list. Do not write mush. Design has no "store the generic words" escape.

Impossible: unknown theme, missing custom folder, pin name not in the would-be `cv.sections`, entry or bullet pins, templates, `render_command`, new `cv.sections` titles, rewriting `cv` prose. Invalid identifier (`Harvard`, `blue`): show the allowed form, one re-ask; do not silent-coerce.

One bad piece: re-ask inside the Slice, then drop that piece; the rest continues in this Sitting. Never abort the Sitting for one bad piece.

## Job-agnostic

This skill only changes job-agnostic design and pins. A pasted Job Posting or Gap Report is not a question agenda. Keep any named ask already stated. Do not harvest `bold_keywords` or a theme from the posting. Say that the skill only changes job-agnostic design and pins.
