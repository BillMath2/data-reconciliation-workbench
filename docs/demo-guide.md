# Demonstration, recording, and replay

The P12 demonstration is a **6:18 real-SQL browser recording** with synthetic
female British English Cori narration, English captions, and seven current screenshots.
Listen to the [voice sample](images/p12/voice-preview.mp3),
download [the MP4](images/p12/walkthrough.mp4), read the [transcript](release-narration.json),
or serve the local chapter player:

```powershell
.\scripts\uv.ps1 run --locked python scripts/serve-release.py
```

Open `http://127.0.0.1:8020/`. GitHub displays the HTML source;
serve it locally for playback and caption tracks. Stop the temporary server with
Ctrl+C. It is not the application and needs no credentials.

## Story and provenance

| Approximate time | What is shown |
|---|---|
| 0:00 | Architecture and the 100-to-94 business discrepancy |
| 0:32 | Captured fresh setup, migration repeat, and driver results |
| 1:04 | Operator runs golden input: 100/94 activities, 202/189 units |
| 1:35 | Original unknown-project row, rule, and acknowledgement |
| 2:05 | Saved investigation using labeled offline guidance |
| 2:37 | Corrected source: 98/98 activities and 197/197 units |
| 3:09 | Six resolved findings retain evidence and successor identity |
| 3:39 | Identical corrected retry produces an audited no-op |
| 4:10 | Analyst view and permission boundary |
| 4:41 | Archived reviewed P05A live response, separate from this run |
| 5:13 | Retained P11 restore/recovery and measured query evidence |
| 5:45 | Scope and outstanding expanded-AI release gates |

Exact chapter times are in [recording.json](evidence/p12/recording.json) and drive
the player. Actual actions use a fresh SQL database. Setup, archived AI, and P11
measurement chapters are browser-rendered exhibits of retained evidence. Narration
is synthetic, not Bill's voice. No new paid model request is made. The
[evidence record](evidence/p12/README.md) separates the recording, browser checks,
final helper replay, and historical test baselines.

## Repeat the isolated verification

Start Docker's Linux engine and initialize the ignored demo configuration. The
replay requires Compose support for `!override` (tested with Compose 5.5.1). The
host needs Python/uv and Playwright for browser checks. From the repository root:

```powershell
.\scripts\initialize-demo.ps1
.\scripts\uv.ps1 sync --locked --python 3.12
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.tools\playwright'
.\scripts\uv.ps1 run --locked python -m playwright install chromium
.\scripts\uv.ps1 run --locked python scripts/release-rehearsal.py --output runs/release-check
```

Use a new output directory each time. The helper creates `wb-p12-<random>` with
a fresh SQL volume/network and host ports 8012/8013, applies nine migrations,
exports the catalog, checks runtime/driver behavior, then replays CLI and complete
browser verification in separate databases. Normal port 8000/8001 containers and
history remain separate. Live AI is disabled in child services.

Logs and `rehearsal.json` go into the output directory. Success requires every
step and cleanup to pass. The helper removes only its generated project's
containers/network/volume in `finally`. If the host kills the helper before cleanup,
inspect that manifest's exact project name and override path, then use those same
Compose arguments to shut down that owned project. Never substitute the normal
project name. This replay is not a rerun of the full 386-test SQL suite; use the
[operator verification command](operations-runbook.md#verify-the-installation) for that.

## Generate or replace narration

The current voice is **Cori**, a synthetic female British English voice generated
locally by Piper. The [publisher's model card](https://huggingface.co/rhasspy/piper-voices/blob/c10ece1aade47bb51c153c893d14e5bf8e5b7117/en/en_GB/cori/high/MODEL_CARD)
identifies the voice and its public-domain LibriVox training dataset. Piper is an
optional GPL-licensed production tool, separate from application dependencies.
The [voice update record](evidence/p12/voice-update.json) retains the exact model
revision/hash and chapter timing adjustments. No narration is sent to a cloud service.

Install the optional tools under ignored `.tools/`, then download the voice:

```powershell
.\scripts\uv.ps1 pip install --python .venv\Scripts\python.exe --target .tools/piper piper-tts==1.8.0
.\scripts\uv.ps1 pip install --python .venv\Scripts\python.exe --target .tools/media imageio-ffmpeg==0.6.0
$env:PYTHONPATH = Join-Path (Get-Location) '.tools/piper'
.venv\Scripts\python.exe -m piper.download_voices en_GB-cori-high --download-dir .tools/voices/cori-high
.venv\Scripts\python.exe scripts/narrate-piper.py --model .tools/voices/cori-high/en_GB-cori-high.onnx --ffmpeg .tools/media/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe --output runs/release-narration
```

The downloader uses the publisher's current model. To reproduce this exact revision,
use the pinned model/config URLs and SHA-256 in the voice update record instead.
Use a fresh output directory. The script generates sentence WAVs, resamples them
to 24 kHz mono PCM, and makes small pitch-preserving timing adjustments to fit each
recorded chapter. It refuses excessive acceleration. Other platforms can supply
their own FFmpeg binary path.

To replace only the audio, copy the retained recording metadata into a fresh
output directory and reuse the accepted MP4's video stream:

```powershell
New-Item -ItemType Directory runs/release-revoice
Copy-Item docs/evidence/p12/recording.json runs/release-revoice/recording.json
.venv\Scripts\python.exe scripts/release_media.py --output runs/release-revoice --audio runs/release-narration --ffmpeg .tools/media/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe --video docs/images/p12/walkthrough.mp4
```

This copies H.264 video without re-encoding, replaces its audio stream, and retimes
captions. `media_duration_seconds` in the metadata pads narration to the complete
video duration. Update the voice disclosure in `release-narration.json` when
changing voices. Keep original media until the replacement has been reviewed.

To record a new SQL browser journey, run the Playwright setup above, then use
`release-rehearsal.py --output runs/release-recording --record --audio runs/release-narration --ffmpeg <binary>`.
The recorder verifies a preview before capturing a separate fresh database; tokens
never appear on screen. The Windows `narrate-release.ps1` helper remains available
for the original Microsoft David voice, but is no longer the delivered soundtrack.

Retain synthetic, credential-free review assets in `docs/images/p12` and
`docs/evidence/p12`. Raw WAV/WebM and build logs stay ignored under `runs/`.
`scripts/check-docs.py` verifies links, dictionary coverage, and asset hashes in CI.
CI does not synthesize voice or repeat the six-minute recording.

## Acceptance

P11 CI was user-confirmed green for `901db40`. P12 CI was user-confirmed green for `d69b176`. The subsequent voice
update awaits its own CI check and listening review. The reduced demonstration uses the
accepted P05A example and offline screen guidance. P10's expanded live-model
evaluation and human semantic review remain outstanding. See
[P12 validation](p12-validation.md) and [release limits](release-scope.md).
