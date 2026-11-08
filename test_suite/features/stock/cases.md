# Stock discovery

- Provider boundary tests use explicit HTTP fixtures: Pexels photo credits/key handling,
  Openverse per-file CC metadata and audio endpoint, filtered invalid source links,
  bounded response size, malformed JSON, non-200 errors, missing key and unsupported kinds.
- API tests verify authentication, bounded query/page, configuration conflict and unsupported
  provider/kind. A fixture response never represents live stock availability or verified rights.
- UI opens provider source links and exports metadata; it does not auto-import or approve rights.
  Automated browser coverage of the live search result UI is not yet implemented.
