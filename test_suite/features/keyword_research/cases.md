# Keyword research

| Layer | Coverage |
| --- | --- |
| Unit | Preferred-site link discovery, web supplementation, public URL validation, empty discovery failure, profile uniqueness, search adapter parsing, website-only mode never calls search, explicit publication metadata vs modification/retrieval dates |
| API | Topic preferences persist, keyword-only job creation, date/title/default snapshot, malformed requests and missing source configuration |
| Integration | Discovery → crawl → analysis failure/retry, source mapping after partial crawl failure, saved-source reuse, AI prompt context/citation indices, saved publication date warnings before analysis |
| Screen flow | Real Streamlit AppTest and API/SQLite: keyword submission without URL |
| E2E | Real Chromium, Streamlit, FastAPI and SQLite: save default website, navigate topic hierarchy, submit keyword and reload. Worker is deliberately not started, so no claim of external search/AI validation. |

Offline search/crawler/AI provider fixtures isolate third-party services. Offline success does not establish live Google/DuckDuckGo availability, article freshness, correctness, or paid AI access. E2E can use `TEST_CHROMIUM_EXECUTABLE=/usr/bin/chromium` when a system browser is available; otherwise install Chromium through Playwright.
