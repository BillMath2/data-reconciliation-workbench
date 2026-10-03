"""Assemble local narration/captions over an existing, unmodified browser capture."""

import argparse
import json
import re
import subprocess
import wave
from pathlib import Path


def load_clips(story, audio):
    clips = {}
    for chapter in story["chapters"]:
        parts = []
        for number, text in enumerate(re.split(r"(?<=[.!?])\s+", chapter["text"])):
            with wave.open(str(audio / f"{chapter['id']}-{number}.wav")) as sound:
                assert (sound.getframerate(), sound.getsampwidth(), sound.getnchannels()) == (
                    24000,
                    2,
                    1,
                )
                parts.append((text, sound.readframes(sound.getnframes())))
        clips[chapter["id"]] = parts
    return clips


def render(output, raw, result, clips, ffmpeg, *, copy_video=False):
    elapsed = result["elapsed_seconds"]
    assert 300 <= elapsed <= 420, "Recording must be between five and seven minutes"
    media_duration = max(elapsed + 1, result.get("media_duration_seconds", 0))
    pcm = bytearray(int(media_duration * 24000) * 2)
    cues = ["WEBVTT", ""]

    def stamp(seconds):
        ms = round(seconds * 1000)
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}.{ms % 1000:03}"

    for event in result["chapters"]:
        offset = event["start"] + 0.5
        duration = sum(len(data) / 48000 + 0.25 for _, data in clips[event["id"]])
        assert duration + 0.5 <= event["duration"], "Narration must fit its recorded chapter"
        for text, data in clips[event["id"]]:
            start = round(offset * 24000) * 2
            pcm[start : start + len(data)] = data
            end = offset + len(data) / 48000
            cues.extend([f"{stamp(offset)} --> {stamp(end)}", text, ""])
            offset = end + 0.25
    narration = output / "narration.wav"
    with wave.open(str(narration), "wb") as sound:
        sound.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        sound.writeframes(pcm)
    (output / "captions.vtt").write_text("\n".join(cues), "utf-8")
    video_options = (
        ["-c:v", "copy"]
        if copy_video
        else ["-c:v", "libx264", "-crf", "24", "-preset", "fast", "-pix_fmt", "yuv420p"]
    )
    with (output / "encode.txt").open("w", encoding="utf-8") as log:
        subprocess.run(
            [
                str(ffmpeg),
                "-nostdin",
                "-y",
                "-i",
                str(raw),
                "-i",
                str(narration),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                *video_options,
                "-c:a",
                "aac",
                "-b:a",
                "96k",
                "-movflags",
                "+faststart",
                *([] if copy_video else ["-shortest"]),
                str(output / "walkthrough.mp4"),
            ],
            check=True,
            stdout=log,
            stderr=log,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--ffmpeg", required=True, type=Path)
    parser.add_argument("--video", type=Path, help="Copy the existing MP4 video stream unchanged")
    args = parser.parse_args()
    story = json.loads(Path("docs/release-narration.json").read_text("utf-8"))
    result = json.loads((args.output / "recording.json").read_text("utf-8"))
    assert result["passed"] and not result["preview"]
    if args.video:
        raw = args.video
        assert raw.resolve() != (args.output / "walkthrough.mp4").resolve()
    else:
        (raw,) = list((args.output / "raw").glob("*.webm"))
    render(
        args.output,
        raw,
        result,
        load_clips(story, args.audio),
        args.ffmpeg,
        copy_video=bool(args.video),
    )
    result["voice"] = story["voice_disclosure"]
    for event, chapter in zip(result["chapters"], story["chapters"], strict=True):
        assert event["id"] == chapter["id"]
        event["narration"] = chapter["text"]
    (args.output / "recording.json").write_text(json.dumps(result, indent=2) + "\n", "utf-8")


if __name__ == "__main__":
    main()
