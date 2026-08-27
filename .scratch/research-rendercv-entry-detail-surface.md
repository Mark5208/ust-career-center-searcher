# Research: RenderCV entry detail surface

Question: per official RenderCV schema and docs, which fields exist on experience, education, and project entries beyond highlights? What is writeable as structured entry fields versus bullets-only? This unblocks “detailed” recording: whether holistic vs detailed experience can live in extra RenderCV keys, or only as ordinary highlights. Master CV is RenderCV YAML (ADR-0007).

Primary sources only. Each claim cites the source that owns it. This ticket is entry-level fields on experience / education / project. It does not redo the `cv` vs `design` / `locale` / `settings` vs `assistant.pinned_section_order` family split (issue 28 / `research/rendercv-write-surface`).

Inspected package: `rendercv==2.8` (this repo’s pin is `rendercv>=2.8` in `pyproject.toml`; `uv run` resolved 2.8). Sample Master CV points at the v2.8 JSON Schema. Installed path: `/Users/chenxiuxia/Desktop/ust-career-center-searcher/.venv/lib/python3.14/site-packages/rendercv/`.

## Verdict

There is no `ProjectEntry` type. A section titled `projects` is only a heading. Typical project rows are `NormalEntry` (required `name`). RenderCV infers entry type from characteristic fields, not from the section title. Nine entry types exist; experience / education / project map to `ExperienceEntry` / `EducationEntry` / `NormalEntry`.

Beyond `highlights`, those three types share the same optional complex fields: `date`, `start_date`, `end_date`, `location` (string), `summary` (string), `highlights` (`list[str]`). Identity fields differ:

| Type | Required | Optional identity | Shared optional |
| --- | --- | --- | --- |
| `ExperienceEntry` | `company`, `position` | — | `date`, `start_date`, `end_date`, `location`, `summary`, `highlights` |
| `EducationEntry` | `institution`, `area` | `degree` | same shared optional |
| `NormalEntry` (projects) | `name` | — | same shared optional |

That is the first-class structured surface. There is no first-class nested skills-on-entry, no sub-project list, no extra nested content schema.

Holistic vs detailed therefore has one documented split: `summary` is a single string (role / brief description; default templates render `SUMMARY`); `highlights` is a list of bullet strings (accomplishments). Detailed recording is ordinary `highlights`. Nested bullets are a string convention inside a highlight (`" - "` → sub-bullet), not nested YAML objects. `highlights` items must be strings; `summary` must be a string.

Arbitrary extra keys are allowed (`extra="allow"` / JSON Schema `additionalProperties: true`) and pass this repo’s `validate_tailored_yaml`. Official docs: they are ignored by default unless referenced in `design.templates` as UPPERCASE placeholders. They are not documented first-class content fields. Extra keys are not a second schema for holistic vs detailed experience.

---

## 1. How section titles relate to entry types — no `ProjectEntry`

RenderCV documents nine entry types: `EducationEntry`, `ExperienceEntry`, `NormalEntry`, `PublicationEntry`, `OneLineEntry`, `BulletEntry`, `NumberedEntry`, `ReversedNumberedEntry`, `TextEntry`.

Source: https://docs.rendercv.com/user_guide/yaml_input_structure/cv/

Installed `rendercv==2.8` matches that set. `EntryModel` is the union of those eight models plus `str` for `TextEntry`. `available_entry_type_names` is that list. **`ProjectEntry` is not in the union.**

Source: `.venv/lib/python3.14/site-packages/rendercv/schema/models/cv/section.py` (`EntryModel`, `available_entry_type_names`); same files on GitHub `rendercv/rendercv` tag `v2.8` (`src/rendercv/schema/models/cv/section.py`).

Section keys are titles, not types. “You can use any of the 9 entry types in any section.” Each section must contain only one entry type. Type is inferred from characteristic fields on the entry dict.

Sources: https://docs.rendercv.com/user_guide/yaml_input_structure/cv/ (“Section names are just titles”, “One entry type per section”); `section.py` `get_characteristic_entry_fields` / `get_entry_type_name_and_section_model`; https://docs.rendercv.com/api_reference/schema/models/cv/section/

Characteristic fields dumped from installed v2.8 (`set(model_fields) - fields that appear on more than one type`):

- `ExperienceEntry`: `company`, `position`
- `EducationEntry`: `institution`, `area`, `degree`
- `NormalEntry`: `name`
- `OneLineEntry`: `label`, `details`
- `PublicationEntry`: `title`, `authors`, `doi`, `url`, `journal`
- `BulletEntry`: `bullet`
- `NumberedEntry`: `number`
- `ReversedNumberedEntry`: `reversed_number`

A `projects:` section whose entries have `name` is `NormalEntry`. The same section title with `company`/`position` would be `ExperienceEntry`. Docs describe `NormalEntry` as “a flexible entry for projects, awards, certifications, or anything else,” and the NormalEntry example is `name: Some Project`. YAML with `project:` (not `name:`) under `projects` fails: RenderCV could not match the section with any entry type.

Sources: https://docs.rendercv.com/user_guide/yaml_input_structure/cv/ (`NormalEntry` table and example); characteristic dump and `project:` mismatch from `build_rendercv_dictionary_and_model` on installed v2.8.

This repo’s sample writes `cv.sections.projects` as `name` + optional `date`/`start_date`/`end_date`/`summary`/`highlights` — i.e. `NormalEntry`. Snapshot code treats a `projects` title as the projects bucket and formats `name` entries that way.

Sources: `examples/sample_master_CV.yaml`; `src/job_finding_assistant/candidate_snapshot.py` `_SECTION_ALIASES` / `_format_entry`

---

## 2. `ExperienceEntry` — fields beyond highlights

Official user-guide table:

| Field | Required | Description |
| --- | --- | --- |
| `company` | Yes | Employer name |
| `position` | Yes | Job title |
| `date` | No | Custom date string (overrides start/end) |
| `start_date` | No | Start date |
| `end_date` | No | End date (or `present`) |
| `location` | No | Office location |
| `summary` | No | Role description |
| `highlights` | No | List of accomplishments |

Source: https://docs.rendercv.com/user_guide/yaml_input_structure/cv/

v2.8 Pydantic model: `ExperienceEntry(BaseEntryWithComplexFields, BaseExperienceEntry)`. Identity on `BaseExperienceEntry`: `company: str`, `position: str` (both required). Complex fields inherited: `start_date`, `end_date`, `location: str | None`, `summary: str | None`, `highlights: list[str] | None`. Date on `BaseEntryWithDate`: `date` optional. `ExperienceEntry.model_fields` order: `company`, `position`, `date`, `start_date`, `end_date`, `location`, `summary`, `highlights`.

Sources: `.venv/lib/python3.14/site-packages/rendercv/schema/models/cv/entries/experience.py`; `.../bases/entry_with_complex_fields.py`; `.../bases/entry_with_date.py`; API pages https://docs.rendercv.com/api_reference/schema/models/cv/entries/experience/ and https://docs.rendercv.com/api_reference/schema/models/cv/entries/education/ (shared complex-field module)

JSON Schema `$defs.rendercv__schema__models__cv__entries__experience__ExperienceEntry`: `required: ["company", "position"]`; properties exactly those eight keys; `"additionalProperties": true`; `"title": "ExperienceEntry"`.

Source: https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/schema.json ; this repo’s sample header cites that v2.8 URL.

`highlights` description in the model: “Bullet points for key achievements, responsibilities, or contributions.” Type `list[str] | None`. `summary` is `str | None` (examples are one-sentence role/coursework lines, not lists).

Source: `entry_with_complex_fields.py` Field definitions

Date validator: if `date` is set, `start_date`/`end_date` are cleared; if only `end_date`, it becomes `date`; if only `start_date`, `end_date` becomes `"present"`.

Source: `BaseEntryWithComplexFields.check_and_adjust_dates` in `entry_with_complex_fields.py`

Default classic templates render identity + `SUMMARY` + `HIGHLIGHTS` in the main column, `LOCATION`/`DATE` in the side column. Placeholders documented: `COMPANY`, `POSITION`, `SUMMARY`, `HIGHLIGHTS`, `LOCATION`, `DATE`. No skills-on-entry placeholder.

Source: `rendercv/schema/models/design/classic_theme.py` class `ExperienceEntry` (design templates, not the CV entry model); default `main_column="**COMPANY**, POSITION\nSUMMARY\nHIGHLIGHTS"`

---

## 3. `EducationEntry` — fields beyond highlights

Official user-guide table:

| Field | Required | Description |
| --- | --- | --- |
| `institution` | Yes | School or university name |
| `area` | Yes | Field of study |
| `degree` | No | Degree type (BS, MS, PhD, etc.) |
| `date` | No | Custom date string (overrides start/end) |
| `start_date` | No | Start date |
| `end_date` | No | End date (or `present`) |
| `location` | No | Institution location |
| `summary` | No | Brief description |
| `highlights` | No | List of bullet points |

Source: https://docs.rendercv.com/user_guide/yaml_input_structure/cv/

v2.8 model: `EducationEntry(BaseEntryWithComplexFields, BaseEducationEntry)`. `institution: str`, `area: str` required; `degree: str | None` optional. Same shared date/location/summary/highlights as experience. `EducationEntry.model_fields`: `institution`, `area`, `degree`, `date`, `start_date`, `end_date`, `location`, `summary`, `highlights`.

Sources: `.venv/lib/python3.14/site-packages/rendercv/schema/models/cv/entries/education.py`; `entry_with_complex_fields.py`; https://docs.rendercv.com/api_reference/schema/models/cv/entries/education/

JSON Schema `$defs.rendercv__schema__models__cv__entries__education__EducationEntry`: `required: ["institution", "area"]`; same optional keys; `"additionalProperties": true`.

Validating YAML with only `institution` (no `area`) fails: `cv.sections.education.0.area: This field is required.`

Source: `build_rendercv_dictionary_and_model` against installed v2.8 (same builder this repo wraps in `src/job_finding_assistant/rendercv_validation.py`)

Default classic `education_entry.main_column` is `**INSTITUTION**, AREA\nSUMMARY\nHIGHLIGHTS` plus optional `degree_column`.

Source: `classic_theme.py` class `EducationEntry` (design templates)

---

## 4. Project rows — `NormalEntry`, not a separate type

Official `NormalEntry` table:

| Field | Required | Description |
| --- | --- | --- |
| `name` | Yes | Entry title |
| `date` | No | Custom date string (overrides start/end) |
| `start_date` | No | Start date |
| `end_date` | No | End date (or `present`) |
| `location` | No | Associated location |
| `summary` | No | Brief description |
| `highlights` | No | List of bullet points |

Source: https://docs.rendercv.com/user_guide/yaml_input_structure/cv/

v2.8 model: `NormalEntry(BaseEntryWithComplexFields, BaseNormalEntry)` with `name: str` required, plus the shared complex fields. JSON Schema `$defs.rendercv__schema__models__cv__entries__normal__NormalEntry`: `required: ["name"]`; `"additionalProperties": true`.

Sources: `.venv/lib/python3.14/site-packages/rendercv/schema/models/cv/entries/normal.py`; schema.json; https://docs.rendercv.com/api_reference/schema/models/cv/entries/normal/

Default classic `normal_entry.main_column` is `**NAME**\nSUMMARY\nHIGHLIGHTS`.

Source: `classic_theme.py` class `NormalEntry` (design templates)

YAML with `cv.sections.projects` + `name`/`summary`/`highlights` validates as `NormalEntry` against v2.8 `build_rendercv_dictionary_and_model`.

---

## 5. Structured vs bullets-only — what is first-class

**Structured (typed fields, default-rendered):** identity (`company`/`position`, `institution`/`area`/`degree`, `name`) + dates + `location` (string) + `summary` (string). These are optional except the required identity keys. They are not bullets.

**Bullets-only content field:** `highlights: list[str]`. Official description: bullet points for achievements / responsibilities / contributions. Markdown and Typst are allowed in text fields including highlights.

Sources: user-guide entry tables; `entry_with_complex_fields.py`; https://docs.rendercv.com/user_guide/yaml_input_structure/cv/ “Text Formatting & Features”

**Not first-class on these three types:**

- Skills on an entry (skills in docs are typically a *section* of `OneLineEntry` with `label`/`details`, not a field on experience/education/project).
- Nested project lists under an experience entry.
- Nested highlight objects (`{holistic, detail}`). v2.8 rejects `highlights.0` that is not a string: “Input should be a valid string.”
- `summary` as a list: “Input should be a valid string.”

Sources: OneLineEntry table at the same user-guide URL; `one_line.py` (`label`, `details` only); validation errors from `build_rendercv_dictionary_and_model` on installed v2.8

**Nested bullets inside highlights** are still strings. The renderer splits `" - "` inside a highlight into a sub-bullet. That is not extra YAML structure.

Source: `.venv/lib/python3.14/site-packages/rendercv/renderer/templater/entry_templates_from_input.py` `process_highlights`

**`summary` vs `highlights`:** default templates put both in the main column (`SUMMARY` then `HIGHLIGHTS`). `summary` is processed as a single Markdown admonition block when it sits on its own template line. That is the only documented first-class place for a holistic prose line beside the bullet list.

Sources: `classic_theme.py` default `main_column` strings; `entry_templates_from_input.py` `process_summary`

Official `llms.txt` lists the same shared fields (`date`, `start_date`, `end_date`, `location`, `summary`, `highlights`) for Experience / Education / Normal. It also lists PublicationEntry as having those shared fields; the PublicationEntry *model* does not (`PublicationEntry` inherits `BaseEntryWithDate`, not `BaseEntryWithComplexFields`: `title`, `authors`, optional `summary`/`doi`/`url`/`journal`/`date` — no `location`/`highlights`/`start_date`/`end_date`). Owner for the three types in this ticket is the user-guide tables + Pydantic models, not that llms.txt grouping.

Sources: https://docs.rendercv.com/llms.txt ; `.venv/.../entries/publication.py`

---

## 6. Extra keys — allowed, not a content schema

Entries inherit `BaseModelWithExtraKeys` → Pydantic `extra="allow"`. JSON Schema for the three types sets `"additionalProperties": true`. Official user guide:

> You can add arbitrary keys to any entry. By default, they're ignored, but you can reference them in `design.templates` field.

The documented example is a scalar (`revenue: $5M ARR`). The how-to page shows `tech_stack: Python, Go, Kubernetes` used as `TECH_STACK` in `design.templates.experience_entry.main_column`. `llms.txt`: “Entries also accept arbitrary extra keys (silently ignored during rendering). A typo in a field name will NOT cause an error.”

Sources: https://docs.rendercv.com/user_guide/yaml_input_structure/cv/ “Arbitrary Keys”; https://docs.rendercv.com/user_guide/how_to/arbitrary_keys_in_entries/; https://docs.rendercv.com/llms.txt ; `.venv/lib/python3.14/site-packages/rendercv/schema/models/base.py` `BaseModelWithExtraKeys`; `.../cv/entries/bases/entry.py` `BaseEntry(BaseModelWithExtraKeys)`

v2.8 `build_rendercv_dictionary_and_model` accepts extra scalars (`tech_stack`), extra string lists (`skills: [Python]`), and extra nested lists of dicts (`projects: [{name, summary, highlights}]`) on an `ExperienceEntry`. Acceptance is `additionalProperties: true`, not a documented nested type. Default templates do not mention `TECH_STACK`, `SKILLS`, or nested `PROJECTS`. The template pipeline uppercases `entry.model_dump(...)` keys as placeholders; non-string extra values are not a documented nested renderer.

Sources: installed v2.8 validation this pass; `classic_theme.py` placeholder lists; `entry_templates_from_input.py` (`key.upper(): value for key, value in entry.model_dump(...)`)

Do not invent extra keys as if RenderCV documented them. Extra keys are a design-template hook. They are not first-class holistic/detail fields.

This repo’s Prepare validator uses the same builder (`rendercv.schema.rendercv_model_builder.build_rendercv_dictionary_and_model`) after stripping `assistant.*`. Extra keys that RenderCV accepts will pass Prepare YAML validation too. That does not make them first-class Master CV fields.

Source: `src/job_finding_assistant/rendercv_validation.py`

---

## 7. What this repo writes today (usage, not schema)

ADR-0007: Master CV is RenderCV YAML on disk.

Source: `docs/adr/0007-rendercv-yaml-master-cv.md`

`examples/sample_master_CV.yaml` (example of what this project writes, not the schema):

- education: `institution`, `area`, `degree`, `start_date`, `end_date`, `location`, `highlights` (no `summary`)
- experience: `company`, `position`, `start_date`, `end_date`, `location`, `highlights` (no `summary`)
- projects: `name`, dates, `summary`, `highlights` (no `location` on those rows)
- skills/tools: `OneLineEntry` `label`/`details`, a different section, not fields on experience/education/project

In-app Master CV Enrichment patches **`highlights` only** on an existing entry. New entries add identity (`company`/`position`, `name`, or `institution`) plus optional dates plus `highlights`. It does not write `summary`, `location`, `area`, or `degree`.

Source: `src/job_finding_assistant/enrichment.py` `patch_master_cv_entry` / `_new_entry_dict`

Candidate Snapshot formats identity + dates + highlights; for `name` entries it also inlines `summary` into the head line. Extra keys are not a Snapshot dimension.

Source: `src/job_finding_assistant/candidate_snapshot.py` `_format_entry`

---

## 8. Implication for holistic vs detailed recording

First-class structured fields beyond highlights: identity, dates, `location`, and one `summary` string. Everything else that is still “the work” is `highlights` (list of strings), optionally with `" - "` sub-bullets inside a string.

Holistic vs detailed cannot live in extra RenderCV keys as first-class structure. Extra keys are undocumented-as-content, default-ignored placeholders for `design.templates`. Putting detail there would not render unless design templates were changed — that is the design-pins surface, not an entry-detail schema.

No skill rewrite follows from this.

---

## Fetch gaps

- `https://github.com/Mark5208/ust-career-center-searcher/issues/48` via WebFetch returned GitHub chrome, not the issue body. Body was retrieved with `gh api repos/Mark5208/ust-career-center-searcher/issues/48` (title/question match the ticket text in this file).
- Official docs at docs.rendercv.com are the live site (not pinned to v2.8). Field tables for Experience / Education / Normal match installed v2.8 models. GitHub `main` `entry_with_complex_fields.py` has the same field names as v2.8.
- `https://docs.rendercv.com/llms.txt` groups PublicationEntry with the shared date/location/summary/highlights set. That grouping is **not** used as the owner for this ticket’s three types; PublicationEntry’s model and user-guide table disagree with that grouping (see §5).
- JSON Schema `$defs` keys are the long Pydantic names (`rendercv__schema__models__cv__entries__experience__ExperienceEntry`), not `$defs.ExperienceEntry`. The `"title"` on those defs is `ExperienceEntry` / `EducationEntry` / `NormalEntry`.

---

## Source list

| Source | Owns |
| --- | --- |
| https://docs.rendercv.com/ | RenderCV docs home; YAML example with education `summary`/`highlights` |
| https://docs.rendercv.com/user_guide/yaml_input_structure/ | Four top-level fields (`cv`/`design`/`locale`/`settings`); JSON Schema pointer |
| https://docs.rendercv.com/user_guide/yaml_input_structure/cv/ | Nine entry types; required vs optional tables; section titles ≠ types; Markdown/Typst; arbitrary keys |
| https://docs.rendercv.com/user_guide/how_to/arbitrary_keys_in_entries/ | Extra keys → UPPERCASE `design.templates` placeholders |
| https://docs.rendercv.com/llms.txt | Condensed field tables; extra keys “silently ignored”; PublicationEntry grouping is imprecise |
| https://docs.rendercv.com/api_reference/schema/models/cv/section/ | `EntryModel` union; characteristic-field detection |
| https://docs.rendercv.com/api_reference/schema/models/cv/entries/experience/ | ExperienceEntry fields |
| https://docs.rendercv.com/api_reference/schema/models/cv/entries/education/ | EducationEntry fields; shared `entry_with_complex_fields` validator |
| https://docs.rendercv.com/api_reference/schema/models/cv/entries/normal/ | NormalEntry fields |
| https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/schema.json | JSON Schema: required keys, `additionalProperties: true`, `highlights` as `array` of `string` |
| https://github.com/rendercv/rendercv/blob/v2.8/src/rendercv/schema/models/cv/entries/experience.py | v2.8 ExperienceEntry source |
| `.venv/lib/python3.14/site-packages/rendercv/` (package 2.8) | Installed models, templates, `process_highlights` / `process_summary` |
| `pyproject.toml` (`rendercv>=2.8`) | This repo’s pin |
| `docs/adr/0007-rendercv-yaml-master-cv.md` | Master CV is RenderCV YAML |
| `src/job_finding_assistant/rendercv_validation.py` | This repo wraps `build_rendercv_dictionary_and_model` |
| `examples/sample_master_CV.yaml` | Example of what this project already writes (not the schema) |
| `src/job_finding_assistant/enrichment.py` | In-app Enrichment writes highlights (+ identity on new rows) |
| `src/job_finding_assistant/candidate_snapshot.py` | Snapshot formats identity/dates/highlights; `summary` on `name` rows |
