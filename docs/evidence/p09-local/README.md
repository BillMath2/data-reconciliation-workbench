# P09 local SQL verification — October 2, 2026

This evidence comes from Docker Desktop on the development workstation, using the repository's pinned SQL Server image and the P09 working tree. It is a real SQL run, separate from GitHub Actions acceptance and from live-model evaluation.

- `workbench` was created and migrations 001–008 applied. Repeating setup applied nothing.
- Restricted-login SQL health and driver transaction checks passed.
- [Full test output](sql-checks.txt): **338 passed**, including **52 SQL cases**, with no skips. The existing Starlette/httpx deprecation warning remains.
- The SQL demonstration verified 100 source rows / 94 accepted, then 98 / 98 after correction, and unchanged no-op reuse. API checks verified all six original findings resolved through the recorded successor.
- [Browser verification](browser-verification.json): the complete screen workflow passed against a separate SQL database, including saved investigations, frozen evidence after correction, citations, AI-off mode, role restrictions, escaping, and mobile layout.
- The API was restored to the main `workbench` database and checked again. SQL Server, mock registry, and API were left healthy. The separate browser database is retained locally; test-fixture databases were removed by their existing teardown.

[Provenance](provenance.json) records SQL version, the base commit, fingerprints of the tested working-tree files, database identities, and hashes of the retained logs. No API keys or demo credentials are included. The browser manifest lists actual captures retained locally in ignored `runs/p09-local/ui-sql`; the images are not copied into this evidence directory.

No real AI provider was called. Push the reviewed P09 changes and confirm both CI jobs green before marking the CI gate accepted. See [P09 validation](../../p09-validation.md).
