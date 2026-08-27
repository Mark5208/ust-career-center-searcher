# Authoring write protocol

This file is not a skill. Do not invoke it as `/master-cv-write`. A Master CV Authoring leaf reads this file and runs it to end a non-empty Sitting. The router never runs it.

Rules: ADR-0018. A successful write is a Master CV content change (ADR-0014). Prepare and the tailor never write the Master CV (ADR-0007). No fabricated experience (ADR-0003). This is not a Master CV Enrichment session write (ADR-0017).

## 1. Find the configured Master CV

Read `~/.job_finding_assistant/master_cv_state/master_cv_path.txt`. That file is the Candidate files path pointer. Its stripped contents are the path of the configured Master CV.

- Pointer missing or unreadable → ask the user to set the Master CV path on Candidate files, then stop. Resume only after Candidate files has a path.
- Leave the pointer unchanged.
- Write only the configured Master CV. A YAML path named in chat is not the target.

Done when the pointer yields a path, or the Sitting has stopped.

## 2. Capture the Sitting base

Read the configured Master CV.

- File missing or unreadable → stop. Inventing a file is not allowed.
- First successful read is the Sitting base. Keep those exact bytes.
- Readable but schema-invalid → a repair Sitting may continue; confirm cannot write until validation passes.

Done when the Sitting has a base, or has stopped.

## 3. Accumulate the would-be file

The **would-be file** is the Sitting draft: the exact text that would replace the configured Master CV.

Edit as text from the Sitting base. Preserve comments. Preserve `assistant.pinned_section_order` unless this Sitting's `master-cv-design-pins` leaf is the one changing pins.

The first Authoring `/name` in this conversation opened the Sitting; this run continues it. Further typed leaf `/name`s in this conversation are the same Sitting. A new conversation is a new Sitting and does not inherit the prior draft. The draft is this conversation; there is no Sitting store. Several Slices may accumulate into one draft. One confirm is one Master CV write. Authoring is a Sitting, not a session.

Abort or an empty change list → stop with no write.

Done when the Sitting has a would-be file, or has stopped with no write.

## 4. Confirm

Show a human-readable change list of the whole Sitting draft. Show the full YAML only if the user asks, or if a list would hide a structural change.

Before confirm, always one Enrichment-in-progress reminder: if a Master CV Enrichment session is in progress in the app, finish or abandon it first. There is no Enrichment lock file; the fingerprint (disk bytes versus Sitting base) is the mutex.

When a new `cv.sections` title is not education, experience, work experience, projects, skills, skills/tools, or tools (compared case-insensitively), include a Snapshot-blind warning: that title will not appear on the Candidate Snapshot or in Relevance. The write may still proceed.

Wait for an explicit chat confirm of that change list. A yes to an interview question is not confirm. There is no magic token.

Done when the user has explicitly confirmed the change list, or the Sitting has stopped with no write.

## 5. Validate

Run `validate_tailored_yaml` from `job_finding_assistant.rendercv_validation` on the would-be text, including `assistant`. The function strips `assistant` internally for the RenderCV schema check. Keep the would-be text; the stripped dump is not the file to write.

The would-be file is also invalid when `assistant` has any key other than `pinned_section_order`, or when a pin name is not a current `cv.sections` key.

Invalid → show the schema errors, stay in the Sitting, fix, new confirm. No write.

The change list is the preview. Do not run `rendercv validate`. Do not render a Master PDF.

Done when the would-be file is valid, or the Sitting is waiting on a new confirm.

## 6. Re-check disk, then replace

Read the configured Master CV again. If those bytes are not the Sitting base, refuse. Do not merge. Re-read, rebuild the draft, new confirm.

Write only after confirm and a valid would-be file whose disk still matches the Sitting base.

Replace the whole file: write the would-be text to a sibling temporary file, then replace the Master CV with that file. Never a subset write. Never a whole-mapping YAML round-trip (it drops comments). Write the file on disk; do not call `Assistant` or `patch_master_cv_entry`.

Done when the configured Master CV has been replaced, or the Sitting is waiting on a new confirm.

## 7. After a successful write

Tell the user, in one line, that the next app use will rebuild the Candidate Snapshot, mark Match Assessments Pending, and mark Preparation Packets Stale. Leave the running server untouched.

Done when that line has been said.
