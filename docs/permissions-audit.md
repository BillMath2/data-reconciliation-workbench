# Demo roles and audit inspection (P08)

The server derives the actor and role from a valid local demo session. Request bodies cannot choose either value. Both roles can read the same synthetic demo evidence and, from P09, save investigation artifacts. The operator can also run the two supplied snapshots and acknowledge findings. The explanation adapter receives frozen context and has no database or mutation tools; the application persists its final result and audit event.

| Operation | Anonymous | Analyst | Operator |
|---|---|---|---|
| Screen shell, static assets, process health | Allowed | Allowed | Allowed |
| Sign in with a configured demo token | Allowed with exact Origin and bounded JSON | Same | Same |
| Inspect loads, freshness, reports, findings, citations, audit | Denied | Allowed | Allowed |
| Save an investigation artifact | Denied | Allowed with session CSRF and exact Origin | Same |
| Read saved investigations and their frozen citations | Denied | Allowed | Allowed |
| Run golden/corrected snapshot | Denied | Denied | Allowed with session CSRF, exact Origin, matching date, and reason |
| Acknowledge a finding | Denied | Denied | Allowed with session CSRF, exact Origin, and reason |
| Sign out | No valid session | Allowed with session CSRF and exact Origin | Same |
| Edit source evidence, manually resolve, execute SQL, or invoke an AI repair | No endpoint | No endpoint | No endpoint |

## Inspect an action

Select a recorded load and expand **Who ran this load?**. It shows the initiating actor and the attempt's ordered events. **Next events** and **Previous events** page through the history. A no-op records a distinct attempt and points to the reused publication; its audit view stays on that attempt. A failed run exposes its recorded start and failure. The saved reconciliation remains unavailable for that failed attempt.

The corresponding endpoint is `GET /api/loads/{load_id}/audit?limit=50&offset=0`. Limits cap at 100; offsets cap at 100,000. The response includes `load` metadata and `items`, each with `event_id`, `actor`, `action`, `occurred_at`, and parsed `detail`. Timestamps are recorded by SQL in UTC. Unknown loads return 404. Audit reasons may contain untrusted text and must never be interpreted as HTML or instructions.

Run reasons are saved in the `load_started` event; terminal events identify publication, no-op reuse, or failure. Exception acknowledgement records its original actor/reason once; repeated acknowledgement does not overwrite history. Resolution events identify the successor load and commit atomically with successful publication. The runtime role can insert/read audit events but cannot update or delete them. An inability to save a required audit record prevents the corresponding committed mutation; P11 adds explicit lock-coordinated recovery with an atomic `load_recovered` audit event. This closes an abandoned attempt; successful publication still requires a separate verified retry. See the [recovery runbook](recovery-runbook.md).

## Browser boundary

Use the configured localhost origin exactly. Authenticated writes require an opaque session cookie and its CSRF token. The session expires after an hour, rotates on login, and is revoked on logout or server restart. SameSite cookies complement the explicit Origin/CSRF checks; they are not the sole protection. The design follows [OWASP's CSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

Writes must have one matching Origin, a single `application/json` content type, one valid Content-Length, no transfer encoding, and at most 8,192 actual bytes. The received byte count must match the declaration. The [ASGI middleware](../src/workbench/http_boundary.py) applies those checks before passing the body to JSON parsing, using the receive/send model documented by [Starlette](https://www.starlette.io/middleware/). It also attaches no-store, nosniff, frame denial, no-referrer, and Content Security Policy headers to handled responses and boundary rejections.

The UI inserts source, rule, evidence, and audit values as text. Its policy permits local scripts/styles and rejects inline script execution. Hidden controls improve the analyst experience; endpoint authorization is what prevents writes. The server never sends the configured demo access tokens to the screen, and the browser does not put tokens in local storage.

See [P08 validation](p08-validation.md) for the tests, user-confirmed CI acceptance, and the distinction between local demo identity and production security.

P09 adds one reviewed POST route, `/api/investigations`. It appends an investigation and required audit event atomically; it grants no authority to modify source/curated data or finding lifecycle. Runtime permissions on `ops.Investigation` are SELECT/INSERT only. The server fixes provider choices and constructs evidence/runbook context. There are no caller-supplied prompts, packets, keys, actor names, model names, or tool definitions. See [P09 boundaries and validation](p09-validation.md).
