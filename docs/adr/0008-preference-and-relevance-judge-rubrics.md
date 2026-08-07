# Preference and Relevance judge rubrics

LLM bands for Preference and Relevance follow these criteria (signals defined in [0006-three-assessment-signals.md](0006-three-assessment-signals.md)). Hard Constraint rubrics are out of scope here.

**Status:** accepted

## Input isolation

- **Preference judge** sees only the Preferences file text and the Job Posting (title, employer, detail fields/text). Never the Master CV or Candidate Snapshot.
- **Relevance judge** sees only the Candidate Snapshot and/or Master CV excerpts and the Job Posting. Never the Preferences file.

## Preference (desire)

Coverage of stated likes and avoids; honor ordering or “higher / nice-to-have” language when the user wrote a hierarchy.

- **Strong:** Posting clearly fits most or all high-priority likes, and does not clearly match any explicit avoid/dislike.
- **Mixed:** Partial fit — some likes match and some miss; likes match but an avoid is only mildly/softly present; or priorities conflict so the posting is a compromise. If the posting is silent on a priority, treat that priority as unknown (not a miss); unknowns lean Mixed rather than Weak unless core likes clearly fail.
- **Weak:** Posting mainly misses the likes, or **clearly matches an explicit avoid** — a clear avoid match caps Preference at Weak even when other likes fit (soft “prefer to avoid” wording may allow Mixed). Non-negotiables belong in the Hard Constraints file, not Preferences.

**Output:** Short reason citing which Preferences lines matched, missed, or were unknown against the posting; light Evidence-style pairs (Preferences line ↔ Job Posting excerpt) when useful. No CV Evidence (no CV in inputs). Empty or missing Preferences file → unknown without a judge call.

## Relevance (capability)

Required / must-have / minimum JD language first; preferred / nice-to-have secondary. Evidence-backed only; never invent CV content.

- **Strong:** Core required duties and must-have skills are largely supported by concrete Snapshot/CV excerpts. Nice-to-haves may be partial.
- **Mixed:** Some core requirements evidenced, others missing or only weakly related; or title/level roughly fits but several must-haves lack Evidence. Vague JD leans Mixed (with Evidence noting ambiguity), not Strong.
- **Weak:** Most core requirements lack Evidence, or the role’s core function clearly does not match experience on the CV.

**Conservative adjacency:** Related or transferable experience may support Mixed, not Strong, and only when Evidence names the adjacent thing honestly (no upgrading coursework to production, no title buzzwords without skill Evidence). Strong requires the core of the requirement as written (or clearly equivalent tool in the same family *and* same seniority context with clear Evidence).

**Output:** About three to seven Evidence pairs (Job Posting excerpt + Snapshot/CV excerpt or “not found” + one-line role). The band must be consistent with that Evidence. Do not punish for Preferences; do not apply Hard Constraints inside Relevance.
