# P12 validation: release demonstration and documentation

P11 CI was user-confirmed green for baseline `901db40`. P12 delivers the reduced
release package allowed by the implementation plan: the deterministic workbench,
offline screen investigations, and the previously reviewed P05A live explanation.
**Expanded P10 live-model evaluation and human semantic review remain open.**
P12's new GitHub CI and user review of these materials are pending; this is not
full expanded-assistant release acceptance.

## Delivered

- README led by current SQL-backed screenshots and a narrated six-minute MP4,
  English captions, transcript, and local chapter player.
- Actual browser actions: golden discrepancy, captured source/rule, acknowledgement,
  offline investigation, corrected publication, preserved history, no-op retry,
  and analyst view. Archived AI and P11 measurements are explicitly labeled exhibits.
- Reproducible isolated Compose replay and optional Windows narration/recording
  tools. A local media server exposes only public assets and supports video seeking.
- Current architecture, schema diagram, complete field dictionary, operator
  troubleshooting, recovery/restore instructions, and scope limitations.
- CI checks for local documentation links, catalog field coverage, recording
  metadata, and retained asset integrity. No voice synthesis or paid AI in CI.

## Verification and provenance

The clean replay uses a generated Compose project, private network, empty SQL
volume, and separate host ports. It applied migrations 1-9, repeated setup with
no pending migrations, exported twelve tables/three views, checked runtime and
driver behavior, and executed the CLI golden/corrected/no-op proof. Browser tests
ran against another fresh database. The recording uses a third fresh journey
after preview verification. Cleanup removes only the generated project/volume.

The [retained evidence](evidence/p12/README.md) separates this release replay from
earlier test baselines. Final helper replay, complete browser verification, and
recording assertions pass. The normal workbench remains healthy with its 94-row
historical publication, 98-row corrected publication, and six resolved findings.

Host tests passed **322 tests, with 64 SQL tests skipped**, plus the existing
Starlette/httpx deprecation warning. Lint, formatting, fixture checks, documentation
checks, and whitespace checks passed. P12 did not rerun the complete SQL pytest
suite: the full **386-test/64-SQL/no-skip** result belongs to accepted P11. P12
independently replays real SQL CLI and full browser workflows; no application
business logic or schema migration changed.

Media review checks screenshots and representative decoded frames, loads captions,
seeks through the local player, and decodes the entire H.264/AAC file successfully.
The voice is locally synthesized Microsoft David Desktop, not Bill's voice. Raw
capture time and encoded container duration may differ slightly because of video
finalization; the displayed duration uses actual media metadata. The final MP4
is below 50 MB. Asset hashes and exact times are in the evidence folder.

## Remaining acceptance

1. Commit/push the P12 changes and obtain green CI for that revision.
2. Review the README, narration, video, and documented scope as the delivery package.
3. Separately complete the authorized live-evaluation process and human semantic
   review described in [P10 validation](p10-validation.md) before accepting the
   expanded assistant release. No live P10 request was made during P12.

No release tag, deployment, or external publication was performed. The
[release-scope record](release-scope.md) retains production and AI limitations.
