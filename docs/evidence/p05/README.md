# P05 SQL demonstration evidence

Captured from commit `3bf61d91fa19e19eb5f6d1955c37e8c2dd243b37` on September 29, 2026, using SQL Server `16.0.4295.3`. The user supplied the artifacts from [CI run 36637726571](https://github.com/BillMath2/data-reconciliation-workbench/actions/runs/36637726571) and confirmed both jobs green. Files were reviewed on October 1, 2026.

- [Provenance and file hashes](provenance.json), [recording manifest](recording.json), and [test output: 164 passed](sql-checks.txt).
- [Golden report](golden.json) and [bounded golden evidence](golden-evidence.json): 100 source / 94 accepted, with six explained exclusions. P05A can use this verified packet.
- [Corrected report](corrected.json) and [corrected evidence](corrected-evidence.json): 98/98 activities, 197/197 units.
- [Repeated report](repeat.json) and [repeated evidence](repeat-evidence.json): no-op, same publication and packet.
- [Plain-text transcript](transcript.txt), [real-time asciicast recording](demo.cast), and [33-second rendered replay](../../images/p05/walkthrough.gif).

These are original downloaded synthetic demonstration outputs, not regenerated database results. `is_current` in each report reflects its capture time. The golden report was captured before correction; the demo then verified that the original publication was superseded while its saved evidence remained unchanged. Exception resolution is explicitly not assessed by these packets.

See the [validation record](../../p05-validation.md) for acceptance checks and limitations.
