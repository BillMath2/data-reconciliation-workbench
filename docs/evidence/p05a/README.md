# First AI explanation evidence

These examples explain the same [verified P05 golden packet](../p05/golden-evidence.json). They do not recalculate or modify its database result.

- [Live answer](live.txt) and [JSON result](live.json): actual OpenAI response accepted by count/citation checks and manually reviewed.
- [Offline stub](stub.txt) and [JSON result](stub.json): deterministic, explicitly labeled; no model called.
- [Unavailable result](unavailable.json): network unavailable, deterministic fallback retained.
- [Rejected first response record](rejected-v1.json): failed count validation under the earlier prompt; rejected prose is not retained or presented as accepted output.
- [Provenance, code hashes, usage, and review notes](provenance.json).

Confirmed facts account for all six exclusions and the 13-unit difference. Proposed checks are suggestions, not actions taken. Use the captured reference set when following them. The live answer does not establish upstream root causes, repairs, subsequent reruns, or exception resolution. Only the single accepted example was manually evaluated; broader evaluation remains P10.

See [P05A validation](../../p05a-validation.md) and [CLI instructions](../../assistant.md).
