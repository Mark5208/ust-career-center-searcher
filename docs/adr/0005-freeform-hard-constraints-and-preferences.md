# Freeform Hard Constraints and Preferences files

Hard Constraints are user non-negotiables; Preferences are soft priorities. Both are authored as separate plain-text files on disk (tool reads only; paths set like the Master CV) so users can express arbitrary deal-breakers and wants without a fixed form. Empty or missing files yield unknown without a judge call. Hard Constraint outcomes are interpreted by the LLM (pass / fail / unknown + reason), not hand-coded language/location/Gap Tolerance rules. The structured Preferences form in ADR-0002 is removed; Crawl Filters stay separate. Hard Constraint judge criteria: [0010-hard-constraint-judge-rubric.md](0010-hard-constraint-judge-rubric.md).

**Status:** accepted (supersedes [0002-preferences-for-hard-constraints.md](0002-preferences-for-hard-constraints.md))

**Considered Options:** Keep structured languages/locations/Gap Tolerance for deterministic tests; freeform HC only / structured Preferences; single combined text file with sections. Rejected structured forms for expressiveness; rejected one file so each input stays manageable for the LLM judge.
