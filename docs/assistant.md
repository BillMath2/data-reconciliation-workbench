# First AI explanation (P05A)

P05A explains the saved golden discrepancy through the CLI. It has a deterministic offline stub and an OpenAI Responses API adapter. It receives a bounded evidence packet and has no SQL connection, database credentials, tools, or repair path. The default is offline.

## Try the saved example

From the repository root in PowerShell:

```powershell
.\scripts\uv.ps1 sync --locked --python 3.12
.\scripts\uv.ps1 run --locked workbench explain --packet docs/evidence/p05/golden-evidence.json --provider stub --format text
```

This prints **OFFLINE STUB**, the recorded 100/94 counts, the six excluded rows grouped by reason, and the 13-unit difference. No environment file or database is required. The [stub example](evidence/p05a/stub.txt) and [reviewed live answer](evidence/p05a/live.txt) use the same saved packet.

For an explicit live request, set `OPENAI_API_KEY` in your process or an ignored environment file. Existing files are not loaded automatically; process values take precedence. Never put the key in a command argument or commit it. Create the output directory first and use a new filename:

```powershell
New-Item -ItemType Directory -Path runs/p05a -Force | Out-Null
.\scripts\uv.ps1 run --locked workbench --env-file .env explain --packet docs/evidence/p05/golden-evidence.json --provider openai --output runs/p05a/my-live-explanation.json --format text
```

`--output` saves JSON metadata and the answer even when the display format is text. Existing output files are rejected before any provider call. Default stdout format is JSON. Exit codes: `0` for a stub or validated live answer, `2` for argument errors, `4` for an invalid packet/file operation, and `6` for unavailable or rejected AI output. Unavailable output still includes deterministic counts and guidance. If a file operation fails after reserving an output, use a new filename for the next attempt.

## Bounded provider request

- Provider: OpenAI; model snapshot `gpt-4.1-mini-2025-04-14`. Azure and other providers are not implemented in this slice.
- One request per invocation, no automatic retries; 30-second total deadline plus HTTP timeouts.
- Input packet at most 64 KiB; provider response at most 32 KiB; output at most 1,800 tokens.
- Preflight request budget: $0.05, using a conservative byte-based input estimate plus an allowance for protocol overhead, and the configured output cap. This is an estimate at reviewed model rates, not an account billing limit. Pricing changes require reviewing the constants.
- `store=false`, no tools, fixed HTTPS endpoint, no redirects, and no ambient proxy configuration.
- Structured JSON output, followed by local validation; incomplete output, refusal, HTTP errors, malformed JSON, unknown citations, and mismatched counts all produce an unavailable state.
- Result metadata includes provider/model, prompt version, packet hash, evidence IDs, latency, attempt count, outcome, and token usage when returned. Keys and raw provider errors/responses are not exported. Rejected prose is discarded.

The adapter uses the documented [Responses structured-output format](https://developers.openai.com/api/docs/guides/structured-outputs) and [GPT-4.1 mini snapshot and rates](https://developers.openai.com/api/docs/models/gpt-4.1-mini), reviewed October 1, 2026. The successful acceptance response used 3,370 input and 852 output tokens, about $0.002711 at uncached rates; this is not a billing statement.

## Evidence and validation boundaries

This first slice accepts the complete P05 golden-discrepancy packet shape: completed activities, known totals, complete findings, and the three supported exclusion rules. It rejects malformed, oversized, missing, partial, or unsupported evidence before a provider call. Corrected/clean snapshots and general questions are outside this CLI slice; their deterministic reports remain available through `reconcile` and `evidence`.

All ten structured metric values and every exclusion reason's row/unit totals must match the packet exactly. Quantitative prose is disallowed through prompt instructions and limited numeric-text checks. Structured citations must resolve; numeric facts must cite the packet's reconciliation record. Source content is JSON data in the user input, never a system instruction. The stub never echoes raw source text.

The answer separates confirmed facts, possible causes, missing evidence, and suggested next checks. Local checks catch basic unsupported action claims, but do not prove arbitrary prose is true or eliminate prompt injection. Human review remains required. In the accepted example, possible-causes prose restates the observed rules; it does not establish upstream root causes. Interpret suggested reference checks against the captured fixed reference set. The original packet records neither repair actions nor later reruns nor exception resolution.

P09 implements screen integration, selected runbooks, and persisted investigations in a separate adapter, leaving this golden-only CLI unchanged. See the [screen investigation guide](investigations.md) for clean/incomplete report support, frozen observations, and live opt-in limits. P09 SQL CI acceptance is pending; P10 adds broader repeated-model, injection, and semantic evaluations. CI uses deterministic mocked responses and the stub; ordinary CI never uses a live API key.
