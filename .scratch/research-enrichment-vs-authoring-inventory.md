# Research: Enrichment vs Authoring inventory

Question: what does in-app Master CV Enrichment actually capture and write (placement, five dimensions, highlights, one-entry patch) versus what `master-cv-content-interview` and `master-cv-design-pins` already allow or refuse? What does the current sandbox eval protocol on [Sandbox eval of Master CV Authoring](https://github.com/Mark5208/ust-career-center-searcher/issues/40) already judge? Domain terms: **Master CV Enrichment**, **Master CV Authoring**, **Sitting**, **Slice**, **Authoring write protocol**. Not a family-shape recommendation (fold vs new leaf).

Primary sources only. Each claim cites the source that owns it.

## Verdict

In-app Master CV Enrichment captures a freeform experience, a user-confirmed placement (existing entry or a new entry under an existing experience/projects/education section — not skills, not new section types), then a fixed five-dimension step flow (skip empty; at most one clarifying follow-up per dimension), then an editable full highlights list, then one confirm that patches **only that entry**. Existing-entry writes replace `highlights` only; new-entry writes add identity fields plus highlights. The session is ephemeral. Confirm refuses if the Master CV fingerprint changed. The write path is `Assistant.confirm_enrichment_write` → `patch_master_cv_entry` → `yaml.safe_dump` + atomic replace.

`master-cv-content-interview` already allows that experience/projects/education overlap and a strictly larger `cv` surface: header, any section title, any of RenderCV's nine entry types, add/modify/remove highlights/entries/whole sections, identity on **existing** entries, in-section reorder, user-confirmed new titles. It refuses design/locale/settings/pins, fabrication, and bouncing to Enrichment. Capture is a user-nominated **Slice** gap-fill — not Enrichment's five dimensions, one-entry, or one-follow-up cap. Follow-ups are uncapped; a dump that already fills the Slice skips further questions.

`master-cv-design-pins` allows only `design`, `locale`, selected `settings`, and `assistant.pinned_section_order`. It refuses `cv` prose, new `cv.sections` titles, inventing a theme, and entry/bullet pins. Enrichment never writes that surface.

The Authoring write protocol is one atomic **whole-file** replace of the configured Master CV after an explicit change-list confirm and `validate_tailored_yaml`. It never calls `Assistant` / `patch_master_cv_entry` and never round-trips the mapping (comments would drop). The router never interviews and never writes.

Issue #40 already judges two ordinary Sittings on `private/eval_master_CV.yaml` as **Sitting met** / **Sitting missed**: protocol success (change-list confirm, `validate_tailored_yaml`, atomic replace), Candidate files pointer unchanged, no `Assistant` / `patch_master_cv_entry`, no unsolicited whole-Master-CV audit; Sitting 1 is a dump-filled new Johnson Electric `experience` entry (not the five dimensions); Sitting 2 is `design.theme: sb2nov` only. It does not judge Enrichment's dimension ritual, existing-entry highlight-only patch, skills-list edits, new section types, mixed Sitting, router, or greenfield. Both recorded eval Sittings were Sitting met.

This inventory does not recommend folding Enrichment into a leaf or adding a new leaf.

---

## 1. Glossary — two write paths, different units

**Master CV Enrichment** is a user-started, job-agnostic **in-app** flow: freeform → user-confirmed placement → fixed-dimension step interview → editable full highlights list → confirm write of ordinary entry content. One session writes one entry. Not Prepare, not Crawl, not Master CV Authoring.

Source: `CONTEXT.md` (origin/main); `docs/adr/0017-master-cv-enrichment.md`

**Master CV Authoring** is the user-invoked, job-agnostic HITL **skill family** for changing the Master CV — content, design, and pins — written on Sitting confirm through the Authoring write protocol. Distinct from in-app Enrichment. Do not call Authoring a session (that is Enrichment).

Source: `CONTEXT.md` (origin/main); `docs/adr/0018-master-cv-authoring.md`

**Sitting** on origin/main: one Authoring invoke through abort or one Authoring write protocol confirm — possibly several Slices, one Master CV write. Later ADR-0018 / CONTEXT (commit `4b31d92`, files identical at `3fb8ce5`) sharpen that: the first Authoring `/name` in a **conversation** opens the Sitting; further typed leaf `/name`s in that conversation are the same Sitting; a new conversation is a new Sitting; the draft is that conversation; there is no Sitting store.

Sources: `CONTEXT.md` and `docs/adr/0018-master-cv-authoring.md` on origin/main; same files at `3fb8ce5` for the conversation-scoped wording

**Slice**: the user-nominated scope of one content-interview or design-pins interview inside a Sitting. The interview stops when that request is filled, not when the Master CV is complete.

Source: `CONTEXT.md` (origin/main)

**Authoring write protocol**: the confirm-and-write ritual that ends a non-empty Sitting — explicit chat confirm, then one atomic write of the configured Master CV — not an Enrichment session write.

Source: `CONTEXT.md` (origin/main); `docs/adr/0018-master-cv-authoring.md`

**Sitting met** / **Sitting missed**: eval verdicts that one Authoring Sitting did or did not satisfy the sandbox-eval rubric. Not Hard Constraint pass/fail. Not an "eval Sitting" type. These terms are owned by issue #44's resolution (and a later CONTEXT update on branches that contain `4b31d92`); they are **not** in origin/main `CONTEXT.md`.

Source: https://github.com/Mark5208/ust-career-center-searcher/issues/44#issuecomment (resolution); `.scratch/sitting-pass-or-fail-grill-outcome.md`

ADR-0018's overlap clause (already on origin/main): full overlap on experience/projects/education content is allowed; do not bounce to Enrichment. Authoring may add/modify/remove `cv` content and may create user-confirmed section titles. Enrichment remains one session, one entry, fixed dimensions, and still cannot add new section types.

Source: `docs/adr/0018-master-cv-authoring.md` decision point 6

---

## 2. Enrichment capture — placement, five dimensions, highlights

### Placement

Freeform start: the user describes an experience; not gated on picking from an enrichable-entry list. `Assistant.submit_enrichment_freeform` requires non-empty text, then `LlmCvEnricher.suggest_placement(freeform, master_cv_yaml)`.

Sources: `docs/adr/0017-master-cv-enrichment.md` decision 1–2; `src/job_finding_assistant/assistant.py` `submit_enrichment_freeform`

LLM may suggest an **existing** entry or a **new** entry under an existing section. Allowed sections in code: `experience` | `projects` | `education` (`SectionName`). Skills lists stay hand-edited — the live enricher system prompt says do not place there; `section` parsed outside that triple is `LlmUnavailableError`. No new section types. User must confirm placement. New entries require user-confirmed identity (employer/title/dates or project name/dates). LLM must not silently place or invent structure.

Sources: `docs/adr/0017-master-cv-enrichment.md` decision 2; `src/job_finding_assistant/enrichment.py` `SectionName`, `PlacementSuggestion`; `src/job_finding_assistant/llm_runtime.py` `_ENRICH_PLACEMENT_SYSTEM` and `suggest_placement`; `src/job_finding_assistant/ports.py` `LlmCvEnricher.suggest_placement`

`Assistant.confirm_enrichment_placement` for `mode == "new"`:

- experience: company and position required
- projects: name required
- education: institution (company or name) required
- dates: start and/or end required

Existing-mode confirm does not re-ask identity; it advances to dimensions.

Source: `src/job_finding_assistant/assistant.py` `confirm_enrichment_placement`

Section key matching on write aliases `experience` / `work experience`; `projects`; `education` (case-insensitive). Missing section → error "Enrichment cannot add section types".

Source: `src/job_finding_assistant/enrichment.py` `section_key_in_yaml`, `patch_master_cv_entry`

### Five dimensions

Fixed order in `ENRICHMENT_DIMENSIONS`:

1. `problem_context` — "What problem or context were you working in?"
2. `technical_work` — "What technical work did you do?"
3. `collaboration_leadership` — "How did you collaborate or lead?"
4. `domain_impact` — "What domain or business impact did this have?"
5. `outcomes_metrics` — "What outcomes or metrics can you share?"

Skip empty (`skip_enrichment_dimension`). At most one clarifying follow-up per dimension (`clarifying_followup`; empty/null → advance). Not an open-ended chat. LLM Unavailable keeps ephemeral answers for retry.

Sources: `docs/adr/0017-master-cv-enrichment.md` decision 3, 6; `src/job_finding_assistant/enrichment.py` `ENRICHMENT_DIMENSIONS`, `DIMENSION_PROMPTS`; `src/job_finding_assistant/assistant.py` `submit_enrichment_dimension`, `skip_enrichment_dimension`, `_advance_enrichment_dimension`; `src/job_finding_assistant/llm_runtime.py` `_ENRICH_FOLLOWUP_SYSTEM`

### Highlights

After all five dimension slots (answered or skipped), the tool drafts an **editable full highlights list** (kept existing + new from freeform and dimension answers). User may edit via `set_enrichment_highlights` (stripped non-empty lines). Explicit confirm writes ordinary entry content.

Sources: `docs/adr/0017-master-cv-enrichment.md` decision 4; `src/job_finding_assistant/assistant.py` `_draft_enrichment_highlights`, `set_enrichment_highlights`; `src/job_finding_assistant/ports.py` `draft_highlights`; `src/job_finding_assistant/llm_runtime.py` `_ENRICH_HIGHLIGHTS_SYSTEM`

For existing placement, kept bullets come from `existing_highlights` on the target entry. The live draft prompt: keep existing highlights that remain true; add new bullets only from the user's freeform and dimension answers; never invent employers, dates, titles, skills, or outcomes the user did not affirm.

Sources: `src/job_finding_assistant/enrichment.py` `existing_highlights`; `src/job_finding_assistant/llm_runtime.py` `_ENRICH_HIGHLIGHTS_SYSTEM`

User-confirmed answers only — the LLM must not invent employers, dates, titles, skills, or outcomes the user did not affirm.

Source: `docs/adr/0017-master-cv-enrichment.md` decision 6

---

## 3. Enrichment write — one-entry patch

One Enrichment session = one placement = one write. Session state is ephemeral (process-local `_EnrichmentSession`; no durable resume). Fingerprint the Master CV at session start (`start_enrichment_session`); if it changed before confirm, **refuse** the write, clear the session, require restart (`EnrichmentConflictError`). Prepare/tailor never write the Master CV.

Sources: `docs/adr/0017-master-cv-enrichment.md` decision 5; `src/job_finding_assistant/assistant.py` `_EnrichmentSession`, `start_enrichment_session`, `confirm_enrichment_write`; `tests/test_assistant_enrichment.py` `test_confirm_write_refuses_when_master_cv_changed`

`confirm_enrichment_write` reads the file, calls `patch_master_cv_entry`, then `atomic_write_text` (sibling `*.enrichment-tmp` then replace). After success, step `done` and `_refresh_candidate_file_state` (Snapshot rebuild path).

Source: `src/job_finding_assistant/assistant.py` `confirm_enrichment_write`; `src/job_finding_assistant/enrichment.py` `atomic_write_text`

`patch_master_cv_entry` patches **only the target entry**:

| Placement | What is written |
| --- | --- |
| `existing` | `entry["highlights"] = list(highlights)` only. Company/position/name/dates on that entry are left as they were. |
| `new` experience | append `{company, position, highlights}` plus optional `start_date` / `end_date` |
| `new` projects | append `{name, highlights}` plus optional dates |
| `new` education | append `{institution, highlights}` plus optional dates (`institution` from company or name) |

The function returns `yaml.safe_dump(loaded, sort_keys=False, allow_unicode=True)` — a whole-mapping dump of the loaded YAML, not a surgical text splice. It does not write `design`, `locale`, `settings`, header fields, other entries, or skills lists.

Sources: `src/job_finding_assistant/enrichment.py` `patch_master_cv_entry`, `_new_entry_dict`; `tests/test_assistant_enrichment.py` `test_confirm_write_patches_only_target_entry_highlights`, `test_new_entry_requires_identity_on_confirm`

ADR-0017: Enrichment is not Authoring (skills, Sitting, Authoring write protocol).

Source: `docs/adr/0017-master-cv-enrichment.md` decision 7

---

## 4. `master-cv-content-interview` — allow and refuse

These files are **not** on origin/main. They shipped in #36–#39 and are identical at `3fb8ce5` and `research/hitl-skill-eval-recording`. Citations below are that tree.

### Allow (Surface)

Direct invoke is a valid Sitting on the `cv` surface alone. The interview mutates `cv` only: header, any section title, any of RenderCV's nine entry types. Add, modify, or remove highlights, entries, whole sections, and header fields, including **identity on existing entries**, when the user affirms it. In-section entry reorder when asked. Experience, projects, and education may be deepened here; that overlap with Enrichment is allowed — continue in this Sitting; do not bounce to Enrichment.

Source: `.agents/skills/master-cv-content-interview/SKILL.md` at `3fb8ce5` (Surface; Open the Sitting)

### Capture shape (not Enrichment's ritual)

Typed slice-and-gap-fill of `cv` — **not Enrichment's five dimensions, one entry, or one-follow-up cap**. Ask only what this write still lacks: RenderCV required identity, plus user-affirmed prose for anything added or rewritten. Uncapped follow-ups, stay inside the Slice. If the dump already fills the Slice, skip further questions and go to the Authoring write protocol. Stop when the Slice is filled, not when the Master CV is complete. The user may end the Slice; remaining gaps drop.

Source: `.agents/skills/master-cv-content-interview/SKILL.md` at `3fb8ce5` (§2 Gap-fill the Slice)

### Placement (Slice-scoped)

Propose a section or entry only for pieces in this Slice that are unplaced or ambiguous. Offer an existing entry, or a new title plus one RenderCV type; the user may rename. Already-placed pieces skip placement. One type per section. New titles only when the user names them or confirms a proposal; they stay unpinned. Stay inside the Slice. Do not re-home entries outside the Slice.

Source: `.agents/skills/master-cv-content-interview/SKILL.md` at `3fb8ce5` (Placement)

### Refuse

- Do not edit `design`, `locale`, `settings`, or `assistant.pinned_section_order`. Whole-section order is pins — leave it to `/master-cv-design-pins`. Preserve comments.
- Write only user-affirmed facts. "Make something up," "probably," and copying a fact onto a different entry without a new affirmation: do not write.
- A thin answer to a gap-fill question does not fill that gap and does not overwrite a real bullet (unless the user nominated those exact generic words as the write).
- Identity-only new job/project/school: ask once for a highlight; if none, still write identity.
- Meaning-preserving rewrite when asked: no new skills, tools, metrics, seniority, or outcomes the user did not affirm.
- Job-agnostic: a pasted Job Posting or Gap Report is not a question agenda.
- Do not start `/master-cv-design-pins` from here (one-line bounce).

Source: `.agents/skills/master-cv-content-interview/SKILL.md` at `3fb8ce5` (Surface, Refuse, Job-agnostic)

Write happens only via the Authoring write protocol when this leaf is the one to run it (direct content-only Sitting, or last named leaf in a mixed Sitting).

Source: `.agents/skills/master-cv-content-interview/SKILL.md` at `3fb8ce5` (§3)

---

## 5. `master-cv-design-pins` — allow and refuse

### Allow (Surface)

Mutates `design`, `locale`, selected `settings`, and `assistant.pinned_section_order` only. Nested visual knobs: `page`, `colors`, `typography`, `links`, `header`, `section_titles`, `sections`, `entries`. Settings: `bold_keywords`, `pdf_title`, `current_date`. Stay inside keys the chosen theme's schema already defines. Any of the nine built-in themes; a custom local theme folder only if the file already names it or the user asks and the folder is there. Pins: reorder; add a name only if it is a current `cv.sections` key; unpin; clear. Continue in this Sitting for design and pins; do not bounce to Enrichment.

Source: `.agents/skills/master-cv-design-pins/SKILL.md` at `3fb8ce5` (Surface, Themes, Pins)

### Refuse

- A `cv` edit ask: one line that it belongs in `/master-cv-content-interview`. Do not start that skill from here.
- Do not write `design.templates` or `settings.render_command`. Leave `cv.sections` key order as it is.
- Do not pick a theme, a measurement, or a pin order the user did not name. Do not invent a custom theme or a palette.
- Theme switch: write the new `design.theme`; drop other `design.*` knobs unless the user asked to keep a specific one.
- If the file has no `design.theme` and the user only names knobs, leave theme unset; do not insert `theme: classic`.
- Impossible: unknown theme, missing custom folder, pin name not in `cv.sections`, entry or bullet pins, new `cv.sections` titles, rewriting `cv` prose.
- Design has no "store the generic words" escape. Do not render a Master PDF.
- Job-agnostic: do not harvest `bold_keywords` or a theme from a pasted Job Posting.

Source: `.agents/skills/master-cv-design-pins/SKILL.md` at `3fb8ce5` (Surface, Themes, Pins, Refuse, Job-agnostic)

Enrichment never captures or writes this surface (no `design` / pins fields in `patch_master_cv_entry`).

Source: `src/job_finding_assistant/enrichment.py` `patch_master_cv_entry`

---

## 6. Authoring write protocol vs Enrichment write

Shared protocol file (not a skill). Router never runs it.

Source: `.agents/skills/master-cv-write-protocol.md` at `3fb8ce5`; `docs/adr/0018-master-cv-authoring.md` decision 1, 4, 5

| Rule | Enrichment session write | Authoring write protocol |
| --- | --- | --- |
| Target | Master CV path already on the Enrichment session (`start_enrichment_session` from `MasterCvStore`) | Configured Master CV from Candidate files pointer `~/.job_finding_assistant/master_cv_state/master_cv_path.txt`. A YAML path named in chat is not the target. Do not write the pointer. |
| Base / mutex | Fingerprint at session start; if disk changed, refuse, clear session, restart | First successful read is the Sitting base (exact bytes). After confirm, if disk ≠ base: refuse, no merge, rebuild, new confirm. Fingerprint is the mutex with Enrichment (no lock file); always remind that an in-progress Enrichment session should finish or abandon first. |
| Confirm | Explicit Enrichment confirm write of the highlights draft | Explicit chat confirm of the Sitting's **change list**. A yes to an interview question is not confirm. |
| Validation | Not a `validate_tailored_yaml` gate in `confirm_enrichment_write` | `validate_tailored_yaml` on the would-be text (including `assistant`). Invalid → no write, stay in the Sitting. Do not run `rendercv validate`. Do not render a Master PDF. Extra `assistant.*` keys or pin names not in `cv.sections` are invalid. |
| What is written | Subset: one entry (highlights; identity if new) via `patch_master_cv_entry` then `yaml.safe_dump` | Whole-file replace of the would-be text. Never a subset write. Never a whole-mapping YAML round-trip (it drops comments). |
| Who writes | `Assistant.confirm_enrichment_write` | The leaf that runs the protocol. Never `Assistant` / `patch_master_cv_entry`. Router never writes. |
| Scope per confirm | One session, one placement, one entry | Several Slices may accumulate into one draft. One confirm is one Master CV write. Empty change list or abort → no write. |
| After write | `_refresh_candidate_file_state` in-process | Tell the user the next app use will rebuild Snapshot, mark Match Assessments Pending, and mark Preparation Packets Stale. Leave the running server untouched. |

Sources: `src/job_finding_assistant/assistant.py` `confirm_enrichment_write`; `src/job_finding_assistant/enrichment.py` `patch_master_cv_entry`, `atomic_write_text`; `.agents/skills/master-cv-write-protocol.md` at `3fb8ce5` §§1–7; `docs/adr/0018-master-cv-authoring.md` decision 4

---

## 7. Router — classify only

`master-cv-authoring` is the index when the user is unsure or wants both. Classify and hint leaf `/name`(s). The user types them. Do not start the leaves from the router. No gap-fill. No Master CV audit. Never run the Authoring write protocol. Never write. Mixed ask = one Sitting; last named leaf runs the protocol once when every named piece is filled or dropped.

Source: `.agents/skills/master-cv-authoring/SKILL.md` at `3fb8ce5`; `docs/adr/0018-master-cv-authoring.md` decision 1–2, 5

---

## 8. Capture/write overlap (inventory only)

| Capture or write | Enrichment | content-interview | design-pins |
| --- | --- | --- | --- |
| Freeform / dump start | Required freeform; LLM then suggests placement | User's first speech nominates the Slice (intent or dump); dump may skip questions | First speech nominates Slice (theme id, knob, locale, settings, or pin list) |
| Placement existing vs new under existing experience/projects/education | Yes; user confirm; new needs identity + dates | Yes, but only for unplaced Slice pieces; already-placed skip | No (`cv` is the other leaf) |
| New `cv.sections` titles / new section types | Refuse | Allow when user names or confirms; stay unpinned | Refuse new titles |
| Skills lists | Hand-edited; do not place | Allow (nine entry types; add/modify/remove) | No |
| Header / other `cv` fields | Not patched | Allow when affirmed | No |
| Identity on an **existing** entry | Not written (highlights only) | Allow when affirmed | No |
| Five fixed dimensions + one-follow-up cap | Yes; skip empty | Explicitly not that ritual; uncapped Slice gap-fill | N/A |
| Highlights list | LLM draft (kept + new); user-editable; confirm write | Add/modify/remove when affirmed; identity-only new entry may have no highlight | No |
| Remove entries / whole sections / in-section reorder | No | Yes when affirmed | No |
| `design` / locale / selected settings / pins | Never | Refuse (one-line bounce) | Only this surface |
| One-entry patch vs whole file | One-entry patch (`safe_dump` of loaded mapping) | Whole-file replace via protocol | Whole-file replace via protocol |
| `Assistant` / `patch_master_cv_entry` | The write path | Never | Never |
| Job-agnostic | Yes | Yes | Yes |
| Unit | One session, one entry | Slice inside a Sitting; several Slices → one write | Slice inside a Sitting |

ADR-0018 already states the experience/projects/education **content** overlap is allowed and that Authoring's `cv` mutation set is larger (add/modify/remove, new titles) while Enrichment stays one session, one entry, fixed dimensions, no new section types.

Source: this table is a join of §§2–6 owners, not a new decision

---

## 9. What #40 already judges

Canonical owner: [Sandbox eval of Master CV Authoring](https://github.com/Mark5208/ust-career-center-searcher/issues/40) (closed). Children 41–45 are closed. Local `.scratch/master-cv-authoring-eval/map.md` is a copy of charting notes and still says remaining open work is #45; GitHub #40 comments supersede that (sandbox exists; Sitting 1 and Sitting 2 recorded **met**).

### Write target (#42, #45)

Eval Sittings are ordinary Sittings. Authoring still writes the configured Master CV from Candidate files. No chat-named YAML. File: `private/eval_master_CV.yaml` (gitignored). Not `examples/sample_master_CV.yaml`. Not the live Master CV. Human retargets Candidate files at the sandbox, then restores. Authoring does not write the pointer. Leave the app up. Do not Crawl, Prepare, Enrichment, or catalog-assess while the sandbox is configured.

Sources: https://github.com/Mark5208/ust-career-center-searcher/issues/42 (resolution comment); https://github.com/Mark5208/ust-career-center-searcher/issues/45 (resolution); `.scratch/sandbox-write-target-grill-outcome.md`

#45 created the sandbox by copying the sample and replacing the header. Recorded live restore path: `/Users/chenxiuxia/Desktop/ust-career-center-searcher/examples/sample_master_CV.yaml`. Sandbox path: `/Users/chenxiuxia/Desktop/ust-career-center-searcher/private/eval_master_CV.yaml`.

Source: https://github.com/Mark5208/ust-career-center-searcher/issues/45 (resolution)

### Scripts (#43)

Two ordinary Sittings, direct leaves, same sandbox file. No mixed Sitting, no greenfield, no router.

- **Sitting 1** — new conversation, `/master-cv-content-interview`. First speech nominates Slice Johnson Electric only: home under the existing `experience` section (placement skipped); identity and three bullets from Mark5208/CV `sections/experience.tex` (cite, don't copy). If that dump fills the Slice, skip further questions and run the Authoring write protocol. Chat `edead6d4-8d25-4576-a6e8-4bba8f9b80f7` is that dump plus a **negative control** (fail if Authoring opens a whole-Master-CV audit). Not an interview template. Not a RenderCV layout spec.
- **Sitting 2** — new conversation, `/master-cv-design-pins`. First speech: set theme to `sb2nov` only. No knobs, locale, settings, or pins. Do not invent a theme. Do not map `TLCresume`.

Sources: https://github.com/Mark5208/ust-career-center-searcher/issues/43 (resolution); `.scratch/first-sitting-script-grill-outcome.md`

### Sitting met / Sitting missed (#44, #41)

Judgment word: **Sitting met** or **Sitting missed**. Hard Constraint keeps pass/fail. No third campaign verdict. No `evals.json` / pytest Sitting harness (#41): record `.scratch/eval-sitting-N-outcome.md` plus a one-line #40 comment; a later recorder who was not the Authoring writer.

**Met** requires Authoring write protocol success on `private/eval_master_CV.yaml` (explicit change-list confirm, `validate_tailored_yaml`, atomic replace). Abort, empty change list, or never reaching a valid write is **missed**. Extra `rendercv validate` / Master PDF is not a signal.

**Hard list** (any miss → missed; nothing else is a signal):

Both Sittings:

- Protocol succeeds on the configured sandbox file only
- Candidate files pointer unchanged; no write to the live Master CV, `examples/sample_master_CV.yaml`, or a chat-named YAML
- No `Assistant` / `patch_master_cv_entry`; no unsolicited whole-Master-CV audit

Sitting 1:

- New `experience` entry under existing `experience` (placement skipped): identity plus the three dump bullets
- Human first speech is dump only — no fourth task, no `projects` entry; at most one in-Slice identity gap-fill
- Scripted piece not dropped; no unaffirmed extras; no `design` / `locale` / `settings` / pins; no edits to other entries or sections

Sitting 2:

- Writes `design.theme: sb2nov` (add); does not invent a theme
- Does not write knobs, locale, settings, or pins; does not edit `cv`; leaves `assistant.pinned_section_order`

Sources: https://github.com/Mark5208/ust-career-center-searcher/issues/44 (resolution); https://github.com/Mark5208/ust-career-center-searcher/issues/41 (resolution); `.scratch/sitting-pass-or-fail-grill-outcome.md`

### Recorded outcomes

Sitting 1 **met**. Sitting 2 **met**. Checklists in `.scratch/eval-sitting-1-outcome.md` and `.scratch/eval-sitting-2-outcome.md` match the hard list (Sitting 1: new Johnson Electric `experience` entry, three dump highlights, pointer unchanged, no `Assistant` / patch; Sitting 2: `design.theme: sb2nov` only).

Sources: https://github.com/Mark5208/ust-career-center-searcher/issues/40 comments; `.scratch/eval-sitting-1-outcome.md`; `.scratch/eval-sitting-2-outcome.md`

#40 out of scope (map body): redesigning in-app Enrichment; writing the live configured Master CV; JD-steered or Gap-Report-shaped interview questions; using the LaTeX CV repo as the write target; changing Prepare / Tailored CV write rules; adding a router Sitting to this eval.

Source: https://github.com/Mark5208/ust-career-center-searcher/issues/40 body (Out of scope)

---

## 10. What #40 does not judge (gaps, not a recommendation)

The eval protocol does **not** exercise or grade:

- Enrichment's five-dimension step flow, skip-empty, or one-follow-up cap
- Enrichment placement confirm (LLM suggest existing vs new) — Sitting 1 **skips** placement because the dump homes the entry
- Enrichment existing-entry **highlights-only** patch (Sitting 1 is a **new** experience entry)
- Skills-list edits, header edits, deletes, in-section reorder, new section titles (content-interview allows; Sitting 1 forbids other entries/sections)
- Mixed Sitting, router classify-and-hint, greenfield from-scratch dossier
- Authoring comment preservation vs Enrichment `yaml.safe_dump`
- Concurrent Enrichment session vs Authoring fingerprint mutex beyond the protocol's reminder line
- Family-level "skills-only parity" with Enrichment (that is map #46; #40 says current-skill eval stays here and must not be reopened)

Sources: join of §9 hard list / #43 scripts / #40 out of scope with §§2–6 allow/refuse; https://github.com/Mark5208/ust-career-center-searcher/issues/46 body (current-skill eval stays on #40)

---

## Fetch gaps

- Authoring skill files and the conversation-scoped Sitting glossary are **not** on `origin/main` (`8f58fe8`). They live at `3fb8ce5` (`research/portable-skill-loading` / `research/hitl-skill-eval-recording`). This findings branch was created from `origin/main` as instructed; skill claims cite `3fb8ce5`.
- `Sitting met` / `Sitting missed` are not in origin/main `CONTEXT.md`. Owner: issue #44 resolution (and later CONTEXT on those research branches).
- Local `.scratch/master-cv-authoring-eval/map.md` still lists #45 as remaining open work. GitHub issue #40 comments record #45 closed and both eval Sittings **met**. GitHub is treated as the index.
- Grill-outcome files under `.scratch/` are cited only where a GitHub resolution comment points at them as "Detail". They are not a second spec.

---

## Source list

| Source | Owns |
| --- | --- |
| `CONTEXT.md` (origin/main) | Enrichment vs Authoring vs Sitting vs Slice vs Authoring write protocol (pre-conversation-scope Sitting) |
| `CONTEXT.md` / `docs/adr/0018-master-cv-authoring.md` at `3fb8ce5` | Conversation-scoped Sitting; no Sitting store |
| `docs/adr/0017-master-cv-enrichment.md` | Enrichment flow, dimensions, one-entry write, not Authoring |
| `docs/adr/0018-master-cv-authoring.md` (origin/main) | Family split, write protocol, overlap allowed, Enrichment stays one session / one entry / fixed dimensions |
| `src/job_finding_assistant/enrichment.py` | `ENRICHMENT_DIMENSIONS`, placement types, `patch_master_cv_entry`, `atomic_write_text` |
| `src/job_finding_assistant/assistant.py` Enrichment methods | Session start, freeform, placement confirm, dimensions, highlights, confirm write, fingerprint refuse |
| `src/job_finding_assistant/ports.py` `LlmCvEnricher` | Placement / follow-up / highlights-draft port |
| `src/job_finding_assistant/llm_runtime.py` enricher prompts | Skills-list not a placement; one follow-up; highlights from affirmed answers |
| `tests/test_assistant_enrichment.py` | Existing-entry highlights-only; new-entry identity; fingerprint refuse |
| `.agents/skills/master-cv-content-interview/SKILL.md` at `3fb8ce5` | `cv` allow/refuse; not five dimensions; Slice gap-fill |
| `.agents/skills/master-cv-design-pins/SKILL.md` at `3fb8ce5` | Design/pins allow/refuse |
| `.agents/skills/master-cv-write-protocol.md` at `3fb8ce5` | Confirm, validate, whole-file replace, never `Assistant` / patch |
| `.agents/skills/master-cv-authoring/SKILL.md` at `3fb8ce5` | Router classify-and-hint; never write |
| https://github.com/Mark5208/ust-career-center-searcher/issues/40 | Eval map; out of scope; Sitting 1/2 met comments |
| https://github.com/Mark5208/ust-career-center-searcher/issues/41 | Recorder shape (`.scratch/` markdown + GitHub comment) |
| https://github.com/Mark5208/ust-career-center-searcher/issues/42 | Sandbox write target |
| https://github.com/Mark5208/ust-career-center-searcher/issues/43 | First Sitting scripts |
| https://github.com/Mark5208/ust-career-center-searcher/issues/44 | Sitting met/missed hard list |
| https://github.com/Mark5208/ust-career-center-searcher/issues/45 | Sandbox copy paths |
| https://github.com/Mark5208/ust-career-center-searcher/issues/46 | Parent map: current-skill eval stays on #40 |
| `.scratch/eval-sitting-1-outcome.md` / `eval-sitting-2-outcome.md` | Recorded hard-signal checklists |
| `.scratch/master-cv-authoring-eval/map.md` | Local charting copy (stale vs GitHub on #45) |
