# Architecture — Job Finding Assistant

## Runtime shape

- **UI:** FastAPI + Jinja, single-user local server (`job_finding_assistant.web.app`).
- **Application seam:** `Assistant` — the only surface the UI and automated tests call.
- **Persistence:** SQLite via `CatalogStore` (Job Postings, Preferences; later Match Assessments / Preparation Packet metadata).
- **Master CV:** LaTeX on disk via `DiskMasterCvStore` (path + Candidate Snapshot rebuild; never overwrites the `.tex` file).
- **Job Board:** Playwright `JobBoardSession` (User-Attended Login + Crawl); faked in tests.
- **LLM ports:** `LlmJudge` (Relevance / Evidence), `LlmCvTailor` (Gap Report / Tailored CV / Edit Summary); faked in tests.

```
Browser → FastAPI/Jinja → Assistant → CatalogStore (SQLite)
                              ├→ JobBoardSession
                              ├→ MasterCvStore (DiskMasterCvStore)
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

CREATE TABLE IF NOT EXISTS preferences (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    languages_json TEXT NOT NULL,
    locations_json TEXT NOT NULL,
    gap_tolerance TEXT
);
```

`listing_status` and `deadline_status` follow glossary values (Open/Closed; Upcoming/Passed/Unknown).
`gap_tolerance` is `None` / `Semester` / `Year` / `Any`, or SQL NULL when unset.
Assessment and Preparation Packet tables arrive in later slices.

## Package layout

```
src/job_finding_assistant/
  assistant.py            # Assistant + AssessmentSummary (+ Preferences re-exports)
  preferences.py          # Preferences, LanguagePreference, GapTolerance
  candidate_snapshot.py   # CandidateSnapshot + LaTeX section parse
  master_cv_store.py      # DiskMasterCvStore (path state; read-only Master CV)
  catalog_store.py        # SQLite CatalogStore
  ports.py                # Protocols for adapters
  fakes.py                # Test / local-shell fakes
  web/
    app.py                # create_app(assistant), main()
    templates/            # Jinja pages (catalog + candidate)
tests/                    # Behavior through Assistant (+ UI→Assistant)
```

## Candidate / Preferences UI

- `/` — Assessment Summary list
- `/candidate` — set Master CV path, inspect Candidate Snapshot, edit Preferences
- POST `/candidate/master-cv`, POST `/candidate/preferences` — mutate only via Assistant

## How to run

```bash
pip install -e ".[dev]"
job-finding-assistant          # http://127.0.0.1:8000
pytest
```
