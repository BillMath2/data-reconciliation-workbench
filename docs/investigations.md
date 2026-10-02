# Saved screen investigations (P09)

The **Explain this evidence** panel saves an explanation of a recorded publication or an inspected finding in that publication. Analysts and operators can create these artifacts. The assistant cannot ingest data, acknowledge findings, resolve exceptions, or execute SQL. P05A's golden-only CLI remains unchanged.

## Use the panel

Apply migration 008 and rebuild the API with Docker running:

```powershell
docker compose --env-file .env.workbench --profile tools run --build --rm migrate
docker compose --env-file .env.workbench --profile web up -d --build --wait api
```

1. Sign in, select a load with a saved reconciliation, and optionally inspect a finding.
2. Choose **Selected load** or **Inspected finding in selected publication**. A finding from another publication is rejected, even when the date filter makes it visible.
3. Leave **Offline guidance** selected, or choose **AI off**. Neither contacts a provider. Choose **Save investigation**.
4. Inspect confirmed facts, possible causes, missing evidence, suggested checks, and the selected versioned runbooks with responsible owners. Click a citation to read the evidence saved with this investigation.
5. After source correction, select the original attempt and reopen its history. The old investigation retains its original facts and observed lifecycle state. Create a new investigation to capture later state.

Clean reports and incomplete totals are supported. Unknown units remain unknown, and incomplete statuses remain labeled. Failed loads without saved reconciliation cannot create an investigation in P09; their findings and audit remain available in the existing inspector. Choose the retained publication to investigate its report. There is no free-form chat or arbitrary packet submission.

## Live provider choice

Live AI requires both `WB_AI_LIVE_ENABLED=true` and `OPENAI_API_KEY` in the API's explicit configuration/environment, followed by an API restart. Compose passes these optional values only to the API service; offline is the default. An existing key in a different file is not automatically discovered. Keep credentials in ignored configuration or the process environment, never in the browser or committed files.

The user must explicitly select **Live AI** for each investigation (the mode resets to offline on sign-in). The pinned model remains `gpt-4.1-mini-2025-04-14`. The provider receives the frozen synthetic evidence context, never SQL settings or demo tokens. The request uses strict structured output, `store=false`, no tools, a 30-second deadline, 1,800 output tokens, a 32 KiB response cap, zero retries, and a conservative $0.05 per-request estimate limit. Context is capped at 96 KiB; the underlying saved packet remains capped at 64 KiB. Oversized request estimates do not call the provider.

Facts/counts come directly from saved reconciliation, outside model-generated prose. Generated notes must cite supplied IDs; possible causes must be tagged tentative. Unchecked numeric prose, selected repair claims, refusals, invalid schema/citations, and tool output are rejected. Any unavailable or rejected provider result saves deterministic guidance with a visible unavailable state. These checks are not a semantic proof: a cited sentence can still be wrong. Human review and P10's broader repeated-model evaluation remain required. The accepted P05A live example does not validate prompt `p09-1`.

The adapter follows the documented [Responses structured-output format](https://developers.openai.com/api/docs/guides/structured-outputs); the budget uses the selected model's [published token rates](https://developers.openai.com/api/docs/models/gpt-4.1-mini). No live provider call was made during P09 local validation.

## Persistence and boundaries

Migration 008 adds `ops.Investigation`, the twelfth table. Each record stores requested attempt, underlying publication, optional finding, server-derived actor, SQL UTC creation time, context hash, frozen context, and final result. The context includes original packet/rules, report state, dated freshness, bounded selected-finding details, and copies of selected runbooks. Selection comes from recorded rule IDs, using the catalog in `src/workbench/runbooks.py`. The runbook owner identifies who should review a proposed correction; it does not grant authority.

Report, freshness, and finding observations are sequential reads, not one transactionally consistent snapshot. The captured timestamps and boundary label make this explicit. Source strings, detail structures, and event lists are bounded; the original stored packet is not recomputed. A no-op retains its own requested attempt while linking the reused publication. History is scoped to the requested attempt.

The artifact and `investigation_saved` audit event commit together. Runtime SQL permissions allow only SELECT/INSERT on investigations. The result records provider/model, prompt version, evidence IDs, attempts, latency, outcome, limits, and available usage. Provider response bodies and credentials are never stored as diagnostics. Database errors return a redacted 503.

Only one investigation creation runs at a time per API process; contention returns 409. No database connection is held during a provider call. A provider call can finish before persistence fails, or a client can lose the response after a commit. There is no durable background job or automatic retry: refresh history before retrying. A later explicit retry can incur another call. There is a per-request estimate limit, not a cumulative account spend cap. This remains a single-process local demo, not a multi-tenant service.

## API

All routes require a session; creation additionally requires exact Origin, bounded JSON, and the session CSRF token. Both roles can create an investigation artifact. Source ingestion and acknowledgement remain operator-only.

| Route | Behavior |
|---|---|
| `GET /api/investigations/capabilities` | Whether live calls are enabled; no credential values |
| `POST /api/investigations` | `load_id`, optional `exception_id`, and `provider` (`stub`, `off`, `openai`); no actor, prompt, key, model, path, or caller evidence fields |
| `GET /api/investigations?load_id=UUID` | History for the requested attempt; default limit 25, maximum 100, offset at most 100,000 |
| `GET /api/investigations/{id}` | Complete saved artifact |
| `GET /api/investigations/{id}/evidence/{evidence_id}` | Resolve only within that artifact's frozen packet, observation, or runbooks |

All rendered values use text nodes. Citation URLs are constructed by the screen against authenticated local routes; model text never supplies a navigation destination. See [P09 validation](p09-validation.md) for the successful local SQL/browser checks and the pending GitHub CI gate.
