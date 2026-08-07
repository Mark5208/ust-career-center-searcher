# RenderCV YAML for Master CV and Tailored CV

Master CV and Tailored CV are RenderCV YAML on disk so the user (and LLM tailor) focus on content while RenderCV handles typography and PDF. The tool never overwrites the Master CV; prepare writes a per-posting Tailored YAML then renders PDF via RenderCV. LaTeX as the Master CV format is dropped for v1 (no dual support). Requires Python ≥3.12 for RenderCV. ADR-0003 still applies: reorder, rephrase, emphasize, omit, or rewrite an existing summary only — preserve RenderCV YAML structure/entries, never invent experience.

**Status:** accepted

**Considered Options:** Keep LaTeX Master CV; dual LaTeX + YAML; content-only YAML without RenderCV. Rejected LaTeX for tailor/typesetting cost; rejected dual support to avoid two parsers and two tailor paths.
