# Master CV Authoring

Master CV Authoring is a user-invoked HITL skill family that interviews for job-agnostic facts and writes the Master CV RenderCV YAML on confirm — a second write path beside Master CV Enrichment. Enrichment stays as the in-app flow ([0017-master-cv-enrichment.md](0017-master-cv-enrichment.md)). Prepare/tailor still never write the Master CV ([0007-rendercv-yaml-master-cv.md](0007-rendercv-yaml-master-cv.md)). No fabricated experience ([0003-no-fabricated-cv-content.md](0003-no-fabricated-cv-content.md)). A successful write is a Master CV content change ([0014-assessment-freshness-and-change-detection.md](0014-assessment-freshness-and-change-detection.md)).

**Status:** accepted

## Decision

1. **Family** — Three user-invoked skills: `master-cv-authoring` (router), `master-cv-content-interview` (`cv` content), `master-cv-design-pins` (design, locale, selected settings, pins). The Authoring write protocol is a shared plain file, not a fourth skill. Agents never start Authoring unsolicited. Direct leaf invoke is a valid Sitting on that surface alone.

2. **Split** — Content-interview mutates `cv` only. Design-pins mutates design/locale/selected settings and pins only. The router classifies and hints leaf names; it never interviews, never writes, never fires the leaves. Mixed ask = one Sitting; the last named leaf runs the Authoring write protocol.

3. **Sitting** — Invoke → abort or one Authoring write protocol confirm. May accumulate several Slices into one draft. Empty change list or abort → no write. Do not call Authoring a session (that is Enrichment).

4. **Authoring write protocol** — Find the configured Master CV from the Candidate files path pointer (do not write the pointer; do not write a different YAML named in chat). First successful read is the Sitting base. Explicit chat confirm of the Sitting's change list (not a yes to an interview question). Then validate the would-be file; invalid → no write, stay in the Sitting, new confirm after fix. Atomic whole-file replace. If disk ≠ base after confirm, refuse, no merge, rebuild, new confirm. Fingerprint is the mutex with Enrichment (no lock file); remind that an in-progress Enrichment session should finish or abandon first. Never `Assistant` / `patch_master_cv_entry`. Never persist a stripped dump.

5. **Who writes** — Router never writes. Direct single-surface Sitting: that leaf runs the protocol. Mixed Sitting: last named leaf runs it once when every named piece is filled or dropped.

6. **Not Enrichment** — Full overlap on experience/projects/education content is allowed; do not bounce to Enrichment. Authoring may add/modify/remove `cv` content and may create user-confirmed section titles. Enrichment remains one session, one entry, fixed dimensions, and still cannot add new section types ([0017-master-cv-enrichment.md](0017-master-cv-enrichment.md)).
