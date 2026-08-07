# Hard Constraint judge rubric

LLM criteria for Hard Constraint pass / fail / unknown (signal defined in [0005-freeform-hard-constraints-and-preferences.md](0005-freeform-hard-constraints-and-preferences.md) and [0006-three-assessment-signals.md](0006-three-assessment-signals.md)). Preference and Relevance rubrics remain in [0008-preference-and-relevance-judge-rubrics.md](0008-preference-and-relevance-judge-rubrics.md).

**Status:** accepted

## Input isolation

The Hard Constraint judge sees only the Hard Constraints file text and the Job Posting (title, employer, detail fields/text). Never the Master CV or Candidate Snapshot; never the Preferences file. Non-negotiables are about the job, not capability (Relevance) or desire (Preference).

Empty or missing Hard Constraints file → **unknown** without a judge call (already in the glossary).

## Outcomes and combination

For each applicable Hard Constraints line against the posting:

- **Fail** a line only on a **clear contradiction** with the posting.
- **Unknown** a line when the posting is silent or ambiguous and nothing clearly violates it.
- **Pass** a line only when it is clearly satisfied (or clearly N/A).

Overall outcome precedence:

1. **Fail** if any line fails.
2. Else **unknown** if any applicable line is unknown.
3. Else **pass**.

Unknown never counts as fail. Fail never blocks Prepare; Prepare confirms with the short fail reason ([0013-prepare-flow.md](0013-prepare-flow.md)). Soft or hedged wording in the Hard Constraints file (“prefer not…”) does not belong here — do not fail on soft wants; note that Preferences are the right place.

## Conservative inference

Bias **under-fail** rather than over-fail (false fail is noisy and triggers unnecessary confirm friction).

- Clear contradiction (e.g. “relocate to London, on-site only” vs “Hong Kong or remote”) → fail.
- Broader/vague geography or unstated location → unknown, not fail. Do not stretch synonyms into a fail.
- Soft JD language (“preferred”, “nice to have”) against a hard user ban → default unknown unless the posting clearly still requires the banned thing.

## Output

- Always a **short reason** naming the decisive Hard Constraints line(s) and the posting fact (or “not stated”).
- On **fail** (and useful on unknown): 1–3 light Evidence-style pairs — Hard Constraints line ↔ Job Posting excerpt (or “not stated”) + one-line role. No CV excerpts.
