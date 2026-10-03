# Release scope and outstanding gates

This is a local, single-organization engineering demonstration using synthetic
source records and demo identities. It is not an MSP/channel SaaS deployment.

| Area | Demonstrated | Boundary |
|---|---|---|
| Capture | SQL departments, paginated REST projects, CSV/manifest activities | 10 MiB, 10,000 rows per input; fixed reference set |
| Publication | Atomic full-date replacement, quarantine, exact accounting, no-op identity | One admitted worker; no job queue or concurrent ingestion |
| Evidence | Original bytes, row/rule provenance, historical packets and audit | No archival/retention policy or tamper-proof external audit store |
| Lifecycle | Acknowledgement and verified successor resolution | Keyless/insufficient evidence remains unresolved |
| Access | Local demo roles, server sessions, Origin/CSRF checks | No SSO, MFA, tenant isolation, or internet-facing production setup |
| AI | Reviewed golden CLI example, offline screen investigations, failure checks | Broader live-model scenario evaluation and human review still open |
| Recovery | Abrupt worker exits, audited recovery, actual same-instance backup/restore | No offsite/PITR rehearsal or production recovery SLA |
| Performance | Selected date/unresolved query on 100,000 activities and findings | Query-only set-based fixture; not ingestion throughput or whole-screen SLA |
| Delivery | Reproducible Compose replay and narrated browser demonstration | No deployment, public website, or service operations commitment |

P11 CI was user-confirmed green for `901db40`. P10 CI was user-confirmed green
for `47a79fb`, but those offline checks do not close its live/human-review gates.
The P12 materials can be prepared and reviewed now; the **full expanded assistant
release is not accepted** until the P10 gates and P12 CI/review checks are closed.

No release tag, deployment, or publication to an external service is performed
by the replay script. The maintained [implementation plan](implementation-plan.md)
records milestone dependencies and the [P12 validation record](p12-validation.md)
distinguishes completed local work from remaining acceptance.
