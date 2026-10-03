"""Check local documentation links and retained P12 evidence without SQL or providers."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


def main():
    root = Path(__file__).resolve().parents[1]
    failures = []
    documents = [root / "README.md", *(root / "docs").rglob("*.md")]
    for document in documents:
        content = re.sub(r"```.*?```", "", document.read_text("utf-8"), flags=re.S)
        for target in re.findall(r"\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)", content):
            url = urlsplit(target.strip("<>"))
            if url.scheme or not url.path:
                continue
            resolved = (document.parent / unquote(url.path)).resolve()
            if not resolved.is_relative_to(root) or not resolved.exists():
                failures.append(f"{document.relative_to(root)}: missing local target {target}")

    evidence = root / "docs/evidence/p12"
    schema = json.loads((evidence / "schema.json").read_text("utf-8"))
    dictionary = (root / "docs/data-dictionary.md").read_text("utf-8")
    sections = dict(re.findall(r"### `([^`]+)`\n(.*?)(?=\n### |\Z)", dictionary, re.S))
    for column in schema["columns"]:
        name = column["schema"] + "." + column["object"]
        if f"| `{column['column']}` |" not in sections.get(name, ""):
            failures.append(f"Dictionary missing {name}.{column['column']}")

    for name in ("rehearsal.json", "final-replay.json"):
        rehearsal = json.loads((evidence / name).read_text("utf-8"))
        assert rehearsal["passed"] and rehearsal["completed_at"]
        assert rehearsal["live_ai_enabled"] is False
        assert rehearsal["steps"][-1]["name"] == "owned-stack-cleanup"
        assert all(step["exit_code"] == 0 for step in rehearsal["steps"])
    recording = json.loads((evidence / "recording.json").read_text("utf-8"))
    assert recording["passed"] and not recording["preview"]
    assert recording["mode"] == "live SQL browser recording"
    assert 300 <= recording["elapsed_seconds"] <= 420
    assert len(recording["chapters"]) == 12
    media = json.loads((evidence / "media-qa.json").read_text("utf-8"))
    assert media["passed"] and media["caption_track_loaded"] and media["seek_verified"]
    assert 300 <= media["duration"] <= 420
    provenance = json.loads((evidence / "provenance.json").read_text("utf-8"))
    assert provenance["expanded_ai_release_accepted"] is False
    for relative, expected in provenance["sha256"].items():
        path = (root / relative).resolve()
        assert path.is_relative_to(root)
        data = path.read_bytes()
        if path.suffix in {".json", ".vtt", ".html", ".txt"}:
            data = data.replace(b"\r\n", b"\n")
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            failures.append(f"Retained asset changed: {relative}; review and refresh provenance")
    assert (root / "docs/images/p12/walkthrough.mp4").stat().st_size < 50_000_000
    if failures:
        raise SystemExit("\n".join(failures))
    print(
        f"Documentation verified: {len(documents)} files; "
        "catalog coverage and P12 asset hashes pass."
    )


if __name__ == "__main__":
    main()
