# Research: RenderCV write surface

Question: which Master CV YAML keys are content vs design vs `assistant.pinned_section_order`, and how a skill can validate a direct edit without going through `Assistant`.

Pinned RenderCV version in this repo: `rendercv>=2.8` (`pyproject.toml`). Sample Master CV points at the v2.8 JSON Schema. Claims below are from that tag’s schema/source plus this repo.

## 1. Inventory: content vs design vs pins

RenderCV’s own YAML has **four top-level fields**. Only `cv` is required; the others default.

| Bucket | Top-level key | Owner | On-disk in `examples/sample_master_CV.yaml` |
|---|---|---|---|
| Content | `cv` | RenderCV schema | Present (`name`, header fields, `sections`) |
| Design | `design` | RenderCV schema | **Absent** (defaults to `classic`) |
| Design (i18n / date words) | `locale` | RenderCV schema | Absent (defaults to English) |
| Design (render behavior) | `settings` | RenderCV schema | Absent (defaults) |
| Tool-only pins | `assistant` | This repo (not RenderCV) | Present: `assistant.pinned_section_order` |

Sources: [RenderCV YAML overview](https://docs.rendercv.com/user_guide/yaml_input_structure/); [RenderCVModel](https://docs.rendercv.com/api_reference/schema/models/rendercv_model/); v2.8 schema root `additionalProperties: false` with properties `cv`, `design`, `locale`, `settings` only ([schema.json @ v2.8](https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/schema.json) lines 9546–9568); [`examples/sample_master_CV.yaml`](examples/sample_master_CV.yaml).

`theme` is **not** a top-level key. It is `design.theme`. ([design field docs](https://docs.rendercv.com/user_guide/yaml_input_structure/design/))

### 1.1 Content — `cv` (RenderCV)

`Cv` forbids unknown keys (`BaseModelWithoutExtraKeys` / schema `additionalProperties: false`). Allowed fields ([`cv.py` @ v2.8](https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/src/rendercv/schema/models/cv/cv.py); [cv field docs](https://docs.rendercv.com/user_guide/yaml_input_structure/cv/)):

- Header / identity: `name`, `headline`, `location`, `email`, `phone`, `website`, `photo`, `social_networks` (`network` + `username`), `custom_connections` (`placeholder`, `url`, `fontawesome_icon`).
- Body: `sections` — a **dict**. Keys are section titles (any string). Values are lists of one entry type per section.

Nine entry types ([cv field docs](https://docs.rendercv.com/user_guide/yaml_input_structure/cv/)):

| Type | Discriminating / required fields | Common optional fields |
|---|---|---|
| EducationEntry | `institution`, `area` required; `degree` optional | `date` / `start_date` / `end_date`, `location`, `summary`, `highlights` |
| ExperienceEntry | `company`, `position` required | same date/location/summary/`highlights` |
| NormalEntry | `name` required | same (used for projects in the sample) |
| PublicationEntry | `title`, `authors` required | `doi`, `url`, `journal`, `date` |
| OneLineEntry | `label`, `details` required | — (skills/tools in the sample) |
| BulletEntry | `bullet` required | — |
| NumberedEntry | `number` required | — |
| ReversedNumberedEntry | `reversed_number` required | — |
| TextEntry | a bare string | — (typical for a `summary` section) |

Entry models **allow** extra keys (`BaseModelWithExtraKeys` / schema `additionalProperties: true`). Extra keys are ignored on the PDF unless referenced from `design.templates`. ([`entry.py` @ v2.8](https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/src/rendercv/schema/models/cv/entries/bases/entry.py); [cv docs “Arbitrary Keys”](https://docs.rendercv.com/user_guide/yaml_input_structure/cv/))

Sample Master content shape ([`examples/sample_master_CV.yaml`](examples/sample_master_CV.yaml)):

- `cv.sections.education` → EducationEntry (`institution`, `area`, `degree`, dates, `location`, `highlights`)
- `cv.sections.experience` → ExperienceEntry (`company`, `position`, dates, `location`, `highlights`)
- `cv.sections.projects` → NormalEntry (`name`, dates, `summary`, `highlights`)
- `cv.sections.skills` / `cv.sections.tools` → OneLineEntry (`label`, `details`)

This repo’s Snapshot and Enrichment only understand a subset of those titles:

- Snapshot aliases: `education`, `experience` / `work experience`, `projects`, `skills` / `skills/tools` / `tools` ([`src/job_finding_assistant/candidate_snapshot.py`](src/job_finding_assistant/candidate_snapshot.py) `_SECTION_ALIASES`).
- Enrichment may write only `experience` / `projects` / `education`; “skills lists stay hand-edited”; “no new section types” ([`docs/adr/0017-master-cv-enrichment.md`](docs/adr/0017-master-cv-enrichment.md); [`src/job_finding_assistant/enrichment.py`](src/job_finding_assistant/enrichment.py) `SectionName`).

### 1.2 Design — `design`, `locale`, `settings` (RenderCV)

**`design`** — visual styling. Built-in `theme` values: `classic` (default), `ember`, `engineeringclassic`, `engineeringresumes`, `harvard`, `ink`, `moderncv`, `opal`, `sb2nov`. Theme objects forbid unknown keys. Nested groups on `classic` (same names on the other built-ins): `page`, `colors`, `typography`, `links`, `header`, `section_titles`, `sections`, `entries`, `templates`. ([design docs](https://docs.rendercv.com/user_guide/yaml_input_structure/design/); v2.8 `ClassicTheme` in [schema.json](https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/schema.json); [`design.py` @ v2.8](https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/src/rendercv/schema/models/design/design.py) also allows a **local custom theme folder** named with `[a-z0-9]+` beside the YAML.)

**`locale`** — language strings, not content. `language` plus overrides such as `last_updated`, `month` / `months`, `year` / `years`, `present`, `month_abbreviations`, `month_names`, and schema-only `phrases`. Built-in languages listed in [locale docs](https://docs.rendercv.com/user_guide/yaml_input_structure/locale/). Locale objects forbid unknown keys.

**`settings`** — RenderCV process behavior, not CV prose. Allowed keys ([`settings.py` @ v2.8](https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/src/rendercv/schema/models/settings/settings.py); [settings docs](https://docs.rendercv.com/user_guide/yaml_input_structure/settings/)):

- `current_date` (`YYYY-MM-DD` or `"today"`)
- `bold_keywords` (list of strings auto-bolded in output)
- `pdf_title` (PDF metadata template)
- `render_command` (output paths / `dont_generate_*` / optional split `design`/`locale` files)

Omitting `design` / `locale` / `settings` is valid. The sample Master has none of them.

### 1.3 Tool-only — `assistant.pinned_section_order`

Not in RenderCV’s schema. This repo defines it as optional Master CV metadata the tailor honors and RenderCV must not show on the PDF ([`docs/adr/0009-tailored-cv-formatting.md`](docs/adr/0009-tailored-cv-formatting.md); [`CONTEXT.md`](CONTEXT.md) Tailored CV).

Contract (ADR-0009):

- Shape: top-level `assistant.pinned_section_order` — a list of section names.
- Pinned sections keep their relative ranks; the tailor may reorder only **unpinned** sections after the pinned block.
- Absent or empty → tailor may decide full section order.
- Invalid section names are ignored, with a note in the Edit Summary (`pin_notes`).
- Parked: no pinning of individual entries or bullets.

Sample ([`examples/sample_master_CV.yaml`](examples/sample_master_CV.yaml)):

```yaml
assistant:
  pinned_section_order:
    - experience
    - projects
    - education
    - skills
    - tools
```

The only `assistant.*` key this repo documents or tests is `pinned_section_order`. `strip_assistant_metadata` drops the **entire** top-level `assistant` mapping, not one sub-key ([`src/job_finding_assistant/rendercv_validation.py`](src/job_finding_assistant/rendercv_validation.py)).

## 2. How to validate after a direct edit (no `Assistant`)

There is **no** repo CLI and **no** RenderCV `validate` command. Validation is a Python function. A skill can call it without constructing `Assistant`.

### 2.1 Preferred: this repo’s wrapper (strips pins, then uses RenderCV’s schema)

Import path:

```python
from job_finding_assistant.rendercv_validation import (
    validate_tailored_yaml,
    strip_assistant_metadata,
)
```

`validate_tailored_yaml(yaml_text: str) -> TailoredYamlValidation` (`valid: bool`, `errors: tuple[str, ...]`):

1. `strip_assistant_metadata(yaml_text)` — `yaml.safe_load`, `data.pop("assistant", None)`, `yaml.safe_dump`.
2. `rendercv.schema.rendercv_model_builder.build_rendercv_dictionary_and_model(stripped)`.
3. On `RenderCVUserValidationError`, format each `RenderCVValidationError` as `".".join(schema_location): message`.

Sources: [`src/job_finding_assistant/rendercv_validation.py`](src/job_finding_assistant/rendercv_validation.py); [`tests/test_rendercv_validation.py`](tests/test_rendercv_validation.py); ADR-0013 ([`docs/adr/0013-prepare-flow.md`](docs/adr/0013-prepare-flow.md)).

Despite the name, the function takes any YAML string. It does not require a Tailored CV, a Job Posting, or `Assistant`. `Assistant.prepare` is only one caller ([`src/job_finding_assistant/assistant.py`](src/job_finding_assistant/assistant.py) around the `validate_tailored_yaml(tailor_result.tailored_yaml)` call).

Exact one-shot check (package on `PYTHONPATH` / editable install, `rendercv` installed):

```bash
PYTHONPATH=src python -c "
from pathlib import Path
from job_finding_assistant.rendercv_validation import validate_tailored_yaml
r = validate_tailored_yaml(Path('examples/sample_master_CV.yaml').read_text(encoding='utf-8'))
print(r.valid)
print('\n'.join(r.errors))
"
```

**Do not write `strip_assistant_metadata(...)` back to the Master CV.** That dump drops comments (including the `# yaml-language-server: $schema=...` line) and deletes pins. Use `validate_tailored_yaml` as a **read-only check** on the text you are about to keep, including `assistant:`.

### 2.2 Direct RenderCV API (must strip first)

```python
from rendercv.schema.rendercv_model_builder import build_rendercv_dictionary_and_model
from rendercv.exception import RenderCVUserValidationError

# Pass a string of YAML contents, not a path.
# Leaving top-level `assistant` in will raise RenderCVUserValidationError.
build_rendercv_dictionary_and_model(stripped_yaml_text)
```

Source: [`rendercv_model_builder.py` @ v2.8](https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/src/rendercv/schema/rendercv_model_builder.py). The first argument is the YAML **contents string**. Passing a path-like string is treated as contents (RenderCV issue [#543](https://github.com/rendercv/rendercv/issues/543)).

### 2.3 RenderCV CLI — render, not validate-only

Official CLI commands are only `rendercv new`, `rendercv render`, `rendercv create-theme`. There is no `rendercv validate`. ([CLI reference](https://docs.rendercv.com/user_guide/cli_reference/))

`rendercv render <file.yaml>` validates via the same Pydantic model, then writes PDF/Markdown/HTML/PNG. That is heavier than schema-only, and **fails if `assistant` is still in the file** (see §3). This repo’s PDF path already strips before CLI: [`src/job_finding_assistant/pdf_renderer.py`](src/job_finding_assistant/pdf_renderer.py) writes `strip_assistant_metadata(...)` to a temp file, then `rendercv render <tmp> --output-folder <out>`.

### 2.4 What this is *not*

- **Not** `build_candidate_snapshot`. That is a lenient hand-rolled parser: requires a `cv` mapping and list-shaped known sections; ignores `design` / `locale` / `settings` / `assistant` and unknown section titles. ADR-0013 deferred swapping Snapshot to RenderCV’s real schema ([`docs/adr/0013-prepare-flow.md`](docs/adr/0013-prepare-flow.md); [`src/job_finding_assistant/candidate_snapshot.py`](src/job_finding_assistant/candidate_snapshot.py)).
- **Not** Enrichment’s `patch_master_cv_entry`. That patches one entry and does not call the schema validator ([`src/job_finding_assistant/enrichment.py`](src/job_finding_assistant/enrichment.py)).
- **Not** IDE JSON Schema alone. The sample’s `$schema=.../v2.8/schema.json` is editor autocomplete. Root `additionalProperties: false` will flag `assistant` as invalid in the editor even though this tool keeps it on disk.

## 3. What breaks if `assistant` is left in vs stripped; invalid design

### 3.1 `assistant` left in (on-disk Master CV — the intended state)

| Consumer | Result | Source |
|---|---|---|
| `validate_tailored_yaml` | **OK** — strips first | [`rendercv_validation.py`](src/job_finding_assistant/rendercv_validation.py); [`tests/test_rendercv_validation.py`](tests/test_rendercv_validation.py) `test_validate_tailored_yaml_ignores_assistant_metadata` |
| `RenderCvPdfRenderer.render_pdf` | **OK** — strips first | [`pdf_renderer.py`](src/job_finding_assistant/pdf_renderer.py) |
| `build_rendercv_dictionary_and_model` / `rendercv render` on the raw file | **Fails** — unknown top-level field | `RenderCVModel(BaseModelWithoutExtraKeys)` with `extra="forbid"` ([`base.py`](https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/src/rendercv/schema/models/base.py), [`rendercv_model.py`](https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/src/rendercv/schema/models/rendercv_model.py)); schema root `additionalProperties: false`; test docstring in [`tests/test_rendercv_validation.py`](tests/test_rendercv_validation.py) |
| `build_candidate_snapshot` | **OK** — only reads `cv` | [`candidate_snapshot.py`](src/job_finding_assistant/candidate_snapshot.py) |
| `patch_master_cv_entry` | **Preserves** `assistant` (round-trips the whole mapping) | [`enrichment.py`](src/job_finding_assistant/enrichment.py) |
| Live tailor | Honors pins if present | [`llm_runtime.py`](src/job_finding_assistant/llm_runtime.py) tailor prompt; ADR-0009 |

Leaving `assistant` on disk is required for pins to survive. “Valid RenderCV YAML” for this tool means: **after strip**, the remainder passes RenderCV’s schema. The on-disk file is RenderCV YAML **plus** one tool-only mapping.

### 3.2 `assistant` stripped and written back

- Pins are gone. Next Prepare, the tailor may reorder every section (ADR-0009: absent/empty → full freedom).
- `yaml.safe_dump` also drops comments / schema header.
- RenderCV CLI and schema then succeed (no extra key).

### 3.3 Invalid `design` / `locale` / `settings`

These are part of `RenderCVModel`. After strip, `build_rendercv_dictionary_and_model` validates them. Bad `design.theme`, unknown nested design keys (`ClassicTheme` `additionalProperties: false`), bad locale keys, or bad settings fail `validate_tailored_yaml` with `location: message` lines.

Effects in this repo:

- **Prepare / PDF:** if the tailor copies an invalid `design` into Tailored YAML, `validate_tailored_yaml` fails; one tailor retry; still-invalid → packet kept, PDF missing, `pdf_missing_reasons` = schema lines (ADR-0013; [`assistant.py`](src/job_finding_assistant/assistant.py)).
- **Snapshot / Relevance:** **does not break**. Snapshot never reads `design`. A Master with broken design can still yield a Snapshot and leave Relevance assessable. “Invalid Master CV” in ADR-0014 is the **lenient** parser, not RenderCV’s schema ([`docs/adr/0014-assessment-freshness-and-change-detection.md`](docs/adr/0014-assessment-freshness-and-change-detection.md); ADR-0013 deferral).
- **Enrichment:** does not validate design; will not repair it.

Missing `design` is fine (classic defaults).

### 3.4 Invalid content (`cv`)

Missing required entry fields (e.g. ExperienceEntry without `position`) fail the real schema — covered by [`tests/test_rendercv_validation.py`](tests/test_rendercv_validation.py) `test_validate_tailored_yaml_reports_schema_errors_for_missing_field`. Malformed YAML also fails. Snapshot may still accept some of those files (it does not require `position`). Authoring should treat **schema** validity as the write gate, not Snapshot.

## 4. Keys a design/pins skill may touch vs must not invent

### May touch (design / pins skill)

- `design.theme` — one of the nine built-ins, or a local custom theme folder that actually exists beside the YAML.
- `design.page`, `design.colors`, `design.typography`, `design.links`, `design.header`, `design.section_titles`, `design.sections`, `design.entries`, `design.templates` — only keys the chosen theme’s schema already defines. Copy from [design docs](https://docs.rendercv.com/user_guide/yaml_input_structure/design/) / v2.8 schema; do not invent siblings (`theme` is the discriminator).
- `locale.language` and documented locale override keys.
- `settings.bold_keywords`, `settings.pdf_title`, `settings.current_date` — RenderCV-owned, user-facing typography/metadata.
- `assistant.pinned_section_order` — list of **existing** `cv.sections` keys (sample: `experience`, `projects`, `education`, `skills`, `tools`). Reorder / subset / clear (empty or omit) only.

### Must not invent

- Any top-level key other than `cv`, `design`, `locale`, `settings`, `assistant`. Root `additionalProperties: false` + `extra="forbid"`.
- Any `assistant.*` key other than `pinned_section_order`. Nothing in ADR-0009, CONTEXT, or tests defines another. Extra `assistant` children survive on disk (strip drops the whole map) but are unspecified.
- Pin names that are not current `cv.sections` keys. Schema will not catch this; the tailor ignores them and notes `pin_notes` (ADR-0009). Do not pin entries or bullets (parked).
- New `cv.sections` titles / types. Product rule: “do not invent new section types” (ADR-0009, ADR-0017). RenderCV would accept arbitrary titles; Snapshot/Enrichment would not treat them as education/experience/projects/skills.
- Content fabrication under `cv` (employers, dates, titles, skills, highlights). ADR-0003 / ADR-0017. A design/pins skill should not rewrite entries.
- Nested design/locale/settings keys not in the v2.8 schema (`additionalProperties: false` on those objects).
- A `theme` key at the YAML root.
- Writing `strip_assistant_metadata` output as the new Master CV.
- `settings.render_command` paths as a default authoring target — those are RenderCV CLI output plumbing ([settings docs](https://docs.rendercv.com/user_guide/yaml_input_structure/settings/)), not Master CV design. Only touch if the user asked for split files / output paths.

### Content skill (out of design/pins, listed so the family does not collide)

May edit `cv.*` header fields and `cv.sections` entries/`highlights` using existing entry types. Enrichment already patches **one** target entry’s highlights (and identity if new) via `enrichment.patch_master_cv_entry` and must not be the authoring path for design/pins ([`docs/adr/0017-master-cv-enrichment.md`](docs/adr/0017-master-cv-enrichment.md)).

### Write-then-validate recipe (skill, no `Assistant`)

1. Edit the on-disk Master CV YAML in place (keep `assistant` if pins remain).
2. `result = validate_tailored_yaml(path.read_text(encoding="utf-8"))`.
3. If `not result.valid`, do not leave the write as final — `result.errors` are the schema lines.
4. Do not call `Assistant`, do not run `rendercv render` on the raw file, do not persist the stripped dump.

A later disk edit is observed on the next public `Assistant` use as a Master CV fingerprint change: Snapshot rebuild, all assessments Pending, packets Stale (ADR-0014). That is expected, not a validation failure.

## Sources (primary)

**RenderCV (v2.8, matches `rendercv>=2.8` and the sample `$schema` tag)**

- https://docs.rendercv.com/user_guide/yaml_input_structure/
- https://docs.rendercv.com/user_guide/yaml_input_structure/cv/
- https://docs.rendercv.com/user_guide/yaml_input_structure/design/
- https://docs.rendercv.com/user_guide/yaml_input_structure/locale/
- https://docs.rendercv.com/user_guide/yaml_input_structure/settings/
- https://docs.rendercv.com/user_guide/cli_reference/
- https://docs.rendercv.com/api_reference/schema/models/rendercv_model/
- https://docs.rendercv.com/developer_guide/json_schema/
- https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/schema.json
- https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/src/rendercv/schema/models/base.py
- https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/src/rendercv/schema/models/rendercv_model.py
- https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/src/rendercv/schema/rendercv_model_builder.py
- https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/src/rendercv/schema/models/cv/cv.py
- https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/src/rendercv/schema/models/cv/entries/experience.py
- https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/src/rendercv/schema/models/cv/entries/bases/entry.py
- https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/src/rendercv/schema/models/design/design.py
- https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/src/rendercv/schema/models/settings/settings.py

**This repo**

- `examples/sample_master_CV.yaml`
- `src/job_finding_assistant/rendercv_validation.py`
- `src/job_finding_assistant/pdf_renderer.py`
- `src/job_finding_assistant/candidate_snapshot.py`
- `src/job_finding_assistant/enrichment.py`
- `src/job_finding_assistant/assistant.py` (Prepare calls `validate_tailored_yaml`; not required for a skill)
- `src/job_finding_assistant/llm_runtime.py` (tailor pin instructions)
- `tests/test_rendercv_validation.py`
- `pyproject.toml` (`rendercv>=2.8`)
- `docs/adr/0007-rendercv-yaml-master-cv.md`
- `docs/adr/0009-tailored-cv-formatting.md`
- `docs/adr/0013-prepare-flow.md`
- `docs/adr/0014-assessment-freshness-and-change-detection.md`
- `docs/adr/0017-master-cv-enrichment.md`
- `docs/adr/0003-no-fabricated-cv-content.md`
- `CONTEXT.md` (Master CV / Master CV Authoring / Tailored CV)
