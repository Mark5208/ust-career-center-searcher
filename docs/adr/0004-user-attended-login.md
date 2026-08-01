# User-Attended Login for Crawls

HKUST Job Board access uses DUO, so storing or automating passwords is unreliable and fragile. v1 uses User-Attended Login: the tool opens the browser, the user authenticates, then the user starts the Crawl — no board passwords are stored. This sits alongside ADR-0001: the tool still does not submit applications.
