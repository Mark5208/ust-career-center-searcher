# HKUST Job Board — DOM / CSS research note

Research for issue #4 (Playwright `JobBoardSession` adapter).  
Primary tests still fake `JobBoardSession`; these selectors are for the live adapter only.

## Sources

| Page | Local capture | Live URL pattern |
|------|---------------|------------------|
| Main (filters + list + Next) | `~/Desktop/details of UI/Career Center _ The HKUST.html` | `https://career.hkust.edu.hk/web/job.php` |
| Detail (example) | `~/Desktop/details of UI/System Engineer(86534) _ Career Center _ The HKUST.html` | `https://career.hkust.edu.hk/web/job_detail.php?jp=86534` |

Saved pages include `_files/` asset folders; prefer **class / id / name / href** over one-off CSS from those assets.

---

## Page shell (both)

- Outer: `.career-content-wrapper` → `.career-content`
- Job Board title: `.career-title` (“Job Board”)
- Auth session visible on detail capture: `.career-user-welcome` (“Welcome …”)

---

## 1. Filter UI (main page)

### Containers

- Form: `#job_search_form`
- Collapsible panel: `#search-panel.search-panel`
- Filter body: **`.search-option`** (all multi-selects + three checkboxes + Search/Clear)
- Keywords bar (above filters): `#keywords` + submit `#btn-search`
- Toggle filters: `#showSearchPanel.flip` (“filter option”)

### Seven filter groups (Select2 multi-selects)

Each lives in `.search-option .search-panel-dropdown` as a native `<select multiple>` (class `select2-hidden-accessible`; UI is Select2). Drive by **`name`** / option **value**, or Select2 searchbox placeholders.

| Crawl Filter (glossary) | `<select name>` | Placeholder text |
|-------------------------|-----------------|------------------|
| Business natures | `BN[]` | All Business Natures |
| Job natures | `JN[]` | All Job Natures |
| Employment types | `EMT[]` | All Employment Types |
| Working locations | `WL[]` | All Working Locations |
| Levels of qualification | `awards[]` | All Levels of Qualification |
| Employment modes | `EM[]` | All Employment Modes |
| Languages | `L[]` | All Languages |

Each select starts with a `Clear All …` option (`data-action="clear_all"`).

### Three checkboxes (inside `.search-option .search-panel-dropdown.double-width`)

| Checkbox | `id` / `name` | `value` |
|----------|---------------|---------|
| Talent-Wise Employment Charter | `#TEC` / `TEC` | `1` |
| Active Job (default ON for Crawl Filters) | `#AJOB` / `AJOB` | `1` |
| Non-Chinese speaking students would be considered | `#NCHI` / `NCHI` | `1` |

### Submit / clear

- Apply filters: `button.btn-default` with text **Search** (inside `.search-option`, `type="submit"`)
- Clear: link to `job.php?clear=1` wrapping a Clear All button
- Note: keyword submit `#btn-search` is separate from the filter-panel Search button

### Playwright hints

1. Open filter panel if needed (`#showSearchPanel`).
2. Set options on the hidden `<select multiple>` (or Select2 UI).
3. Set `#AJOB` etc.
4. Click Search in `.search-option`.
5. Wait for `#job-list` to refresh.

Deadline Hardline is **not** a board control — apply in the tool after list discovery.

---

## 2. List rows (main page)

### Container

- Table: `#job-list.job-list`
- Row: `tr.job-item`
- Desktop cells: `td.detail-text.large-view` (use these for large viewport)
- Mobile duplicate layout: `td.small-middle-view` / `.mobile-detail-*` — prefer **`.large-view`** for crawl

### Column order (four `td.detail-text.large-view` per row)

| Index | Header (`.detail-header`) | Content |
|-------|---------------------------|---------|
| 0 | Company / Organization | Employer name; color swatch for employment-type tag |
| 1 | Job Title (+ Job Nature italic) | Title + nature line |
| 2 | Posting Date | `YYYY-MM-DD` |
| 3 | Application Deadline | `YYYY-MM-DD` |

### Open detail (new tab)

- Link: **`a.job-post`** with **`target="_blank"`**
- Href pattern: `https://career.hkust.edu.hk/web/job_detail.php?jp={id}`
- Example: `jp=86534` → System Engineer
- Job Posting id for catalog: query param **`jp`**

### Playwright hints

- Discover: `#job-list tr.job-item`
- Id: parse `a.job-post[href*="job_detail.php?jp="]`
- List fields: `td.detail-text.large-view` nth 0–3 (trim text)
- Detail: `page.context.expect_page()` around click on `a.job-post`, then scrape, then `detail.close()`

---

## 3. Next / pagination (main page)

**Class name is `pagination` (not `progination`).**

```html
<ul class="pagination">
  <li class="active">…</li>
  …
  <li class="next"><a href="…/job.php?page=2&">Next »</a></li>
</ul>
```

| Selector | Role |
|----------|------|
| `ul.pagination` | Pagination bar |
| `li.next > a` | Next page (“Next »”) |
| `li.active` | Current page |
| `li.last > a` | Last page number |
| `li.disabled` | Ellipsis / disabled slot |

### Playwright hints

- After scraping a page: if `ul.pagination li.next a` exists and is enabled, click it; wait for `#job-list` update.
- If `li.next` missing or not clickable → end list discovery.
- Filter query params usually stay on page links (`job.php?page=N&…`); do not assume filters clear on Next.

---

## 4. Detail page

### Shell

- Content root: **`.career-content`** (inside `.content-container`)
- Subtitle: `.career-subtitle` (“Job Details”, later “Job Information”)
- Actions: `.career-action-menu` / `#add-to-job-cart` (ignore for crawl; no auto-apply)

### Summary strip

- Desktop table `.large-view`: headers `.detail-header`, values `.detail-text` — Company, Job Title/Nature, Posting Date, Application Deadline
- Also `.small-middle-view` with **Ref No.** (e.g. `00086534`) — useful cross-check with `jp`

### Structured blocks (label = `.detail-header`, value = `.detail-text`)

Tables: `.second-detail`, `.second-detail2`, `.second-detail3`, `.second-detail4`

Fields seen on System Engineer (86534) include:

- Brand Name, Website, Business Nature, Product / Services, Location of Company Ownership
- Staff counts (HK / worldwide)
- Brief Introduction of the Company / Organization
- Position Offered, No. of vacancies
- Employment Type, Employment Mode, Job Nature
- **Job Description** (Evidence-rich)
- **Work Location**
- Language Requirement (Speaking) / (Writing)
- Other Requirement, Field of Study Required
- Level of Qualification
- Commence Duty in, Employment Period
- Application Method (e.g. email) — scrape for catalog text only; tool must not submit applications (ADR-0001)

Parse by walking `.career-content` rows: read `.detail-header` text → adjacent `.detail-text` HTML/text.

### Close control

```html
<input type="button" class="btn-form" onclick="window.close();" value="Close">
```

- Selector: `input.btn-form[value="Close"]` (or get_by_role button/name Close)
- Behavior: `window.close()` — closes the detail **tab/window**
- Playwright: prefer `detail_page.close()` after scrape; clicking Close is equivalent if the page was opened as a popup/tab

---

## Mapping to domain / adapter

| Domain concept | DOM cue |
|----------------|---------|
| Crawl Filters (7 groups) | `BN[]` `JN[]` `EMT[]` `WL[]` `awards[]` `EM[]` `L[]` |
| Crawl Filters (3 checkboxes) | `#TEC` `#AJOB` `#NCHI` |
| Job Posting id | `jp` on `a.job-post` / `job_detail.php?jp=` |
| Employer | list col0 / detail Company |
| Title | list col1 / detail Job Title |
| Deadline status inputs | list/detail Application Deadline date |
| Evidence text | detail Job Description + Other Requirement (+ other bodies as needed) |
| List discovery pagination | `ul.pagination li.next a` |

## Out of scope for this note

- CSS pixel styling from `_files/*.css` (not required for locators)
- Automating Add to Job Cart / application submit
- Making these selectors the primary pytest suite
