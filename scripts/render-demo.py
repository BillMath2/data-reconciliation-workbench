"""Render recorded CLI text as PNG captures and a paced GIF replay; never generate results."""

import argparse
import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def font(size):
    for path in (
        Path("C:/Windows/Fonts/consola.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def render(recording: Path, destination: Path):
    data = json.loads(recording.read_text("utf-8"))
    if data.get("status") != "verified" or data.get("mode") not in {"sql-server", "ci-baseline"}:
        raise ValueError("Only a verified SQL recording or captured CI baseline can be rendered.")
    frames = data["frames"]
    if not frames or len(frames) > 10:
        raise ValueError("Expected 1-10 recorded frames.")
    wrapped = [
        [
            line
            for original in frame["text"].splitlines()
            for line in (
                textwrap.wrap(original, width=105, replace_whitespace=False, drop_whitespace=False)
                or [""]
            )
        ]
        for frame in frames
    ]
    height = max(720, max(len(lines) for lines in wrapped) * 26 + 220)
    if height > 1800:
        raise ValueError("Recording is too tall for a readable capture.")
    destination.mkdir(parents=True, exist_ok=False)
    images = []
    mode = "P04 verified CI baseline" if data["mode"] == "ci-baseline" else "SQL walkthrough"
    for number, (frame, lines) in enumerate(zip(frames, wrapped, strict=True), 1):
        canvas = Image.new("RGB", (1440, height), "#0d1424")
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(
            (24, 24, 1416, height - 24), radius=18, fill="#131f33", outline="#30435d", width=2
        )
        draw.text((54, 48), "DATA RECONCILIATION WORKBENCH", font=font(24), fill="#eff6ff")
        draw.text(
            (54, 85),
            f"{mode}  |  Recorded CLI output  |  {number}/{len(frames)}",
            font=font(19),
            fill="#a8b8cf",
        )
        draw.line((54, 124, 1386, 124), fill="#30435d", width=2)
        draw.text((54, 145), frame["title"], font=font(20), fill="#63dfb5")
        for index, line in enumerate(lines):
            draw.text((54, 182 + index * 26), line, font=font(20), fill="#e0e9f5")
        canvas.save(destination / f"step-{number}.png")
        images.append(canvas)
    images[0].save(
        destination / "walkthrough.gif",
        save_all=True,
        append_images=images[1:],
        duration=11000,
        loop=0,
        optimize=True,
    )
    # Preserve provenance beside the renders; pacing changes, captured text does not.
    (destination / "recording.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    (destination / "README.md").write_text(
        "# Recorded CLI output\n\n"
        f"Mode: **{mode}**. PNGs render the recorded text; the GIF is a paced replay "
        "(11 seconds per frame), not a desktop screen recording. No counts or load IDs "
        "are invented by the renderer. See recording.json for source/provenance.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    render(args.recording, args.destination)
