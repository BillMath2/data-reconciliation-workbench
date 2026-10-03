"""Generate local Piper narration and fit each chapter to the verified video timing."""

import argparse
import hashlib
import json
import re
import subprocess
import wave
from pathlib import Path

from piper import PiperVoice, SynthesisConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recording", type=Path, default=Path("docs/evidence/p12/recording.json"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    raw = args.output / "raw"
    raw.mkdir()
    story = json.loads(Path("docs/release-narration.json").read_text("utf-8"))
    recording = json.loads(args.recording.read_text("utf-8"))
    voice = PiperVoice.load(str(args.model))
    config = SynthesisConfig(length_scale=0.9)
    timings = []
    for chapter, event in zip(story["chapters"], recording["chapters"], strict=True):
        assert chapter["id"] == event["id"]
        parts = re.split(r"(?<=[.!?])\s+", chapter["text"])
        inputs, seconds = [], 0.0
        for index, sentence in enumerate(parts):
            file = raw / f"{chapter['id']}-{index}.wav"
            with wave.open(str(file), "wb") as sound:
                voice.synthesize_wav(sentence, sound, syn_config=config)
            with wave.open(str(file), "rb") as sound:
                seconds += sound.getnframes() / sound.getframerate()
            inputs.append(file)
        available = event["duration"] - 1.25 - len(parts) * 0.25
        tempo = max(1.0, seconds / available)
        assert tempo <= 1.35, "Narration would need excessive acceleration; review pacing"
        for file in inputs:
            subprocess.run(
                [
                    str(args.ffmpeg),
                    "-nostdin",
                    "-v",
                    "error",
                    "-i",
                    str(file),
                    "-af",
                    f"atempo={tempo:.8f}",
                    "-ar",
                    "24000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(args.output / file.name),
                ],
                check=True,
            )
        timings.append({"chapter": chapter["id"], "raw_seconds": seconds, "tempo": tempo})
        print(f"Generated {chapter['id']}; timing adjustment {tempo:.2f}x", flush=True)
    (args.output / "voice.json").write_text(
        json.dumps(
            {
                "engine": "piper-tts 1.8.0",
                "voice": "en_GB-cori-high",
                "model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
                "length_scale": 0.9,
                "chapters": timings,
            },
            indent=2,
        )
        + "\n",
        "utf-8",
    )


if __name__ == "__main__":
    main()
