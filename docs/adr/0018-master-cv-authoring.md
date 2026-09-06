# Master CV Authoring

Master CV Authoring is a user-invoked HITL skill family that interviews for job-agnostic facts and writes the Master CV RenderCV YAML on confirm — a second write path beside Master CV Enrichment. Enrichment remains the in-app flow until Gate met ([0017-master-cv-enrichment.md](0017-master-cv-enrichment.md)). Prepare/tailor still never write the Master CV ([0007-rendercv-yaml-master-cv.md](0007-rendercv-yaml-master-cv.md)). No fabricated experience ([0003-no-fabricated-cv-content.md](0003-no-fabricated-cv-content.md)). A successful write is a Master CV content change ([0014-assessment-freshness-and-change-detection.md](0014-assessment-freshness-and-change-detection.md)).

**Status:** accepted

## Decision

1. **Family** — Three user-invoked skills: `master-cv-authoring` (router), `master-cv-content-interview` (`cv` content), `master-cv-design-pins` (design, locale, selected settings, pins). The Authoring write protocol is a shared plain file, not a fourth skill. Agents never start Authoring unsolicited. Direct leaf invoke is a valid Sitting on that surface alone.

2. **Split** — Content-interview mutates `cv` only. Design-pins mutates design/locale/selected settings and pins only. The router classifies and hints leaf names; it never interviews, never writes, never fires the leaves, and does not hint Holistic Slice vs Detailed Slice. The content-interview leaf classifies Slice kind from user speech after they type the leaf. Mixed ask = one Sitting; the last named leaf runs the Authoring write protocol.

3. **Sitting** — The first Authoring `/name` in a conversation (router or leaf) opens the Sitting; further typed leaf `/name`s in that conversation are the same Sitting (one accumulated draft, one confirm, one write). Slices in that Sitting may mix Holistic Slice, Detailed Slice, and design-pins; this is not a one-entry cap. A new conversation is a new Sitting and does not inherit the prior draft. The draft is that conversation; there is no Sitting store. Empty change list or abort → no write. Do not call Authoring a session (that is Enrichment).

4. **Authoring write protocol** — Find the configured Master CV from the Candidate files path pointer (do not write the pointer; do not write a different YAML named in chat). First successful read is the Sitting base. Explicit chat confirm of the Sitting's change list (not a yes to an interview question). Then validate the would-be file; invalid → no write, stay in the Sitting, new confirm after fix. Atomic whole-file replace. If disk ≠ base after confirm, refuse, no merge, rebuild, new confirm. Fingerprint is the mutex with Enrichment (no lock file); remind that an in-progress Enrichment session should finish or abandon first. Never `Assistant` / `patch_master_cv_entry`. Never persist a stripped dump.

5. **Who writes** — Router never writes. Direct single-surface Sitting: that leaf runs the protocol. Mixed Sitting: last named leaf runs it once when every named piece is filled or dropped.

6. **Not Enrichment** — Full overlap on experience/projects/education content is allowed; do not bounce to Enrichment. That overlapping job is a Holistic Slice on content-interview. Authoring may add/modify/remove `cv` content and may create user-confirmed section titles. Enrichment remains until Gate met: one session, one entry, fixed dimensions, and still cannot add new section types ([0017-master-cv-enrichment.md](0017-master-cv-enrichment.md)). Layout is not Enrichment's job and is outside the gate.

7. **Slice kinds** — Fold Enrichment's job into `master-cv-content-interview` as Slice kinds. No fourth leaf. No router-classified mode.
   - **Holistic Slice** — one experience, projects, or education entry **and** the user asked to deepen/complete/cover it, or dumped that one entry without naming holes (then skip dump-filled Facets). Required identity for a new or unplaced entry, and identity facts in a deepen/dump about that row, stay inside the Holistic Slice.
   - **Detailed Slice** — named holes, other `cv` (header, skills, multi-entry, delete/reorder), or a one-bullet edit. Does not walk Facets.
   - Ambiguous (“Update X” with no further intent) → one question: walk the Facets, or named holes?
   - Mixed speech → several Slices, not one hybrid ritual. Named hole plus deepen on the same entry → two Slices. Header, skills, or a different entry is always another Slice.
   - Several Slices from one speech run in mention order; if unclear, one question which Slice first.
   - Vague “deepen my experience” with no which-entry → one placement question (existing or new). “Deepen all” is not an audit: one question which experience, projects, or education entries this Sitting (identity list only); each chosen entry is its own Holistic Slice.
   - No in-place conversion of kind. “Actually walk the five” nominates a new Holistic Slice; already-affirmed draft pieces stay. “Just write what we have” during a Holistic Slice skips remaining Facets, not a conversion to Detailed Slice.
   - Classification tell: one line naming kind and target (and the Slice list when there are several), then proceed unless they contradict. Not a dossier audit, not a draft recap, not a wait-for-yes.
   - Placement stays the content-interview rule. No whole-Master-CV gap audit.

8. **Facets and recording** — Offer all five Facets in glossary order. They are interview coverage, not RenderCV keys. Extra keys are not a content schema. Prose lands in optional `summary` plus ordinary `highlights`.
   - Capability bullet on Holistic Slice writes only. A bullet may name a skill or tool only if the user affirmed it. It need not already exist under skills/tools, and Authoring does not infer a skills-section row from it.
   - Offer all five; the user may skip empty. At most one clarifying follow-up per Facet. A thin answer does not fill that Facet, does not mint a highlight, and does not punch up.
   - Existing entry, all Facets skipped: leave `highlights` untouched.
   - New entry, no highlights: identity-only is writeable after one highlight ask.
   - Existing Holistic Slice write: full `highlights` replace — keep bullets that remain true plus new from filled Facets.
   - Dump-filled: skip Facets the dump already answers; offer only remaining empty Facets. If the dump fills all five, draft the full highlights list and go to the Authoring write protocol.
   - Write or replace `summary` only when the user affirms a role one-liner. Leave an existing `summary` untouched otherwise. Do not auto-write `summary` from a problem/context answer.

9. **Design-pins negatives** — Design-pins stays named-write of a user-nominated Slice. No Holistic Slice on layout. No required theme. No opening or closing layout audit. Closing offer is silence (a misfire bounce to the other `/name` is not an offer). Theme, knobs, locale, selected settings, and pins are each independently optional. Absent `design.theme` is complete; do not insert `classic`. Absent or empty pins is complete. Greenfield may never invoke this leaf. Pin names must be keys on the Sitting would-be `cv.sections` at gap-fill, including titles added earlier in this Sitting. Names not yet in the draft: re-ask once, then drop that piece. Do not mint titles from a pin list. Design-pins-first on empty sections drops the pin piece; it does not abort.

10. **Gate** — Keep-Enrichment-until is Gate met: skills-only sufficiency (write a Master CV without `/candidate/enrichment`), not feature-parity with Enrichment and not a full Authoring regression. Gate met means two independent Sitting proofs, either order: a greenfield Sitting from a name-only Master CV (no experience, projects, or education entries) was Sitting met **and** the dossier bar held — `cv.name` plus at least one experience, projects, or education entry whose `highlights` come from a Holistic Slice (skills/tools, theme, knobs, locale, settings, and pins optional) — **and** a separate Sitting that holistically deepened an existing experience entry was Sitting met. The existing-entry Sitting is not judged as greenfield. That pair is the only latch on in-app Enrichment. A later per-skill Sitting missed does not keep Enrichment. Layout is outside the gate. The gate does not cap how many Sittings a greenfield dossier may take.
    Identity-only on the greenfield write (write succeeded, no Capability bullet) is Sitting missed and the dossier bar not held → Gate missed.
    Per-skill eval is a skill-quality bar for a later rewrite, not a second latch: four ordinary Sittings (router write-less, detailed content, refuse-then-named-write, mixed last-named-leaf). Named tests are specified, not run here; fixture YAML and scripted speech stay on the grilling tickets.
