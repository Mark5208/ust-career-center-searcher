# Architecture — Job Finding Assistant

## Runtime shape

- **UI:** FastAPI + Jinja, single-user local server (`job_finding_assistant.web.app`).
- **Application seam:** `Assistant` — the only surface the UI and automated tests call.
- **Persistence:** SQLite via `CatalogStore` (Job Postings, later Match Assessments / Preparation Packet metadata).
- **Master CV:** LaTeX on disk via `MasterCvStore` (not overwritten by the tool).
- **Job Board:** Playwright `JobBoardSession` (User-Attended Login + Crawl); faked in tests.
- **LLM ports:** `LlmJudge` (Relevance / Evidence), `LlmCvTailor` (Gap Report / Tailored CV / Edit Summary); faked in tests.

```
Browser → FastAPI/Jinja → Assistant → CatalogStore (SQLite)
                              ├→ JobBoardSession
                              ├→ MasterCvStore
                              ├→ LlmJudge
                              └→ LlmCvTailor
```

## Database schema (CatalogStore)

Empty catalog is valid. Current SQLite schema:

```sql
CREATE TABLE IF NOT EXISTS job_postings (
    id TEXT PRIMARY KEY,
    title TEXT,
    employer TEXT,
    listing_status TEXT,
    deadline_status TEXT
);
```

`listing_status` and `deadline_status` follow glossary values (Open/Closed; Upcoming/Passed/Unknown). Assessment and Preparation Packet tables arrive in later slices.

## Package layout

```
src/job_finding_assistant/
  assistant.py       # Assistant + AssessmentSummary
  catalog_store.py   # SQLite CatalogStore
  ports.py           # Protocols for adapters
  fakes.py           # Test / local-shell fakes
  web/
    app.py           # create_app(assistant), main()
    templates/       # Jinja pages
tests/               # Behavior through Assistant (+ UI→Assistant)
```

## How to run

```bash
pip install -e ".[dev]"
job-finding-assistant          # http://127.0.0.1:8000
pytest
```
