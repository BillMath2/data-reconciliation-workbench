"""Record a paced, narrated real-SQL browser walkthrough; never synthesize app results."""

import argparse
import html
import json
import os
import time
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright
from release_media import load_clips, render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--ffmpeg", required=True, type=Path)
    parser.add_argument("--setup-evidence", required=True, type=Path)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    story = json.loads(Path("docs/release-narration.json").read_text("utf-8"))
    setup = json.loads((args.setup_evidence / "rehearsal.json").read_text("utf-8"))
    assert all(s["exit_code"] == 0 for s in setup["steps"])
    assert json.loads((args.setup_evidence / "ui/verification.json").read_text())["passed"]
    clips = load_clips(story, args.audio)
    events, screenshots, errors = [], [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            record_video_dir=str(args.output / "raw"),
            record_video_size={"width": 1440, "height": 1000},
        )
        # Authenticate through the API before the page exists: never record the token.
        assert context.request.post(
            args.origin + "/api/session",
            headers={"Origin": args.origin},
            data={"token": os.environ["WB_DEMO_OPERATOR_TOKEN"]},
        ).ok
        assert not context.request.get(args.origin + "/api/loads?limit=1").json()["items"]
        epoch = time.monotonic()
        page = context.new_page()
        page.set_default_timeout(30000)
        page.on("pageerror", lambda error: errors.append(str(error)))

        def ready():
            expect(page.locator("#workbench")).to_have_attribute("aria-busy", "false")

        def card(title, body):
            markup = (
                """<!doctype html><html><meta charset="utf-8"><style>
                body{margin:0;background:#0d1929;color:#edf4ff;font:25px/1.6 Segoe UI,Arial}
                main{padding:65px 85px}h1{font-size:48px;line-height:1.15;margin:24px 0 35px}
                .tag{color:#69debf;font-size:19px;letter-spacing:2px}pre{white-space:pre-wrap;
                font:20px/1.6 Consolas,monospace;background:#172b41;padding:24px;border-radius:14px}
                .row{display:flex;gap:18px}.box{flex:1;background:#172b41;padding:25px;border-radius:15px}
                small{color:#a9bdd5}li{margin:12px 0}</style><main>
                <div class="tag">DATA RECONCILIATION WORKBENCH · BILL MATHERS</div>"""
                + "<h1>"
                + html.escape(title)
                + "</h1>"
                + body
                + "</main></html>"
            )
            page.goto("data:text/html;charset=utf-8," + quote(markup))
            assert (
                page.locator("body").evaluate("e => getComputedStyle(e).backgroundColor")
                == "rgb(13, 25, 41)"
            )

        def shot(name):
            page.screenshot(path=str(args.output / f"{name}.png"), full_page=False)
            screenshots.append(f"{name}.png")

        def run(snapshot, expected):
            page.locator("#snapshot").select_option(snapshot)
            page.locator("#run-reason").fill(
                "Release demonstration: reviewed supplied source snapshot"
            )
            page.get_by_role("button", name="Run snapshot", exact=True).click()
            expect(page.locator("#run-result")).to_contain_text(expected)
            ready()

        saved = finding = original_source = corrected = None
        for chapter in story["chapters"]:
            name = chapter["id"]
            if name == "intro":
                card(
                    chapter["title"],
                    "<p>One hundred source rows. Ninety-four accepted activities.</p>"
                    '<div class="row"><div class="box">SQL departments<br>'
                    "REST projects<br>CSV activities</div>"
                    '<div class="box">Python validation<br>SQL publication<br>Saved evidence</div>'
                    '<div class="box">Operator review<br>Cited investigations<br>'
                    "Audited retries</div></div>"
                    "<p><small>Real SQL-backed browser actions · Synthetic data · "
                    "Synthetic narration</small></p>",
                )
            elif name == "setup":
                results = []
                for file in ("setup", "setup-repeat", "health", "driver"):
                    lines = (args.setup_evidence / f"{file}.txt").read_text("utf-8").splitlines()
                    result = next(
                        json.loads(line) for line in lines if line.startswith('{"status"')
                    )
                    results.append(file + ": " + json.dumps(result))
                card(
                    chapter["title"],
                    "<p>Captured from this rehearsal’s fresh Compose stack.</p><pre>"
                    + html.escape("\n\n".join(results))
                    + "</pre>",
                )
            elif name == "golden":
                page.goto(args.origin)
                ready()
                run("golden", "published with exceptions")
                expect(page.locator("#metrics")).to_contain_text("100 → 94")
                expect(page.locator("#exceptions tr")).to_have_count(6)
                page.evaluate("window.scrollTo(0,0)")
                shot("01-golden")
            elif name == "finding":
                page.locator("#exceptions button").first.click()
                ready()
                finding = page.locator("#evidence-id").inner_text().split(":")[1]
                original_source = page.locator("#source").inner_text()
                page.locator("#detail-title").evaluate("(e) => e.scrollIntoView({block: 'start'})")
                shot("02-finding")
                page.locator("#ack-reason").fill(
                    "Source evidence reviewed; correction still required"
                )
                page.get_by_role("button", name="Acknowledge finding", exact=True).click()
                expect(page.locator("#detail-state")).to_contain_text("ACKNOWLEDGED")
                ready()
            elif name == "investigation":
                page.locator("#investigation-scope").select_option("finding")
                page.locator("#investigate-submit").click()
                expect(page.locator("#investigation-state")).to_contain_text("OFFLINE GUIDANCE")
                ready()
                golden = page.locator("#load").input_value()
                identifier = context.request.get(
                    args.origin + f"/api/investigations?load_id={golden}"
                ).json()["items"][0]["investigation_id"]
                saved = context.request.get(
                    args.origin + f"/api/investigations/{identifier}"
                ).json()
                page.locator("#investigation-title").evaluate(
                    "(e) => e.scrollIntoView({block: 'start'})"
                )
                shot("03-investigation")
            elif name == "correction":
                run("corrected", "published ·")
                expect(page.locator("#metrics")).to_contain_text("98 → 98")
                expect(page.locator("#metrics")).to_contain_text("197 → 197")
                corrected = page.locator("#load").input_value()
                page.evaluate("window.scrollTo(0,0)")
                shot("04-corrected")
            elif name == "history":
                page.locator("#scope").select_option("date")
                ready()
                page.locator("#status").select_option("resolved")
                expect(page.locator("#exceptions tr")).to_have_count(6)
                page.locator(f'#exceptions tr[data-id="{finding}"] button').click()
                expect(page.locator("#detail-state")).to_contain_text("RESOLVED")
                expect(page.locator("#source")).to_have_text(original_source)
                expect(page.locator("#resolution")).to_contain_text(corrected)
                assert (
                    context.request.get(
                        args.origin + f"/api/investigations/{saved['investigation_id']}"
                    ).json()
                    == saved
                )
                page.locator("#detail-title").evaluate("(e) => e.scrollIntoView({block: 'start'})")
                shot("05-history")
            elif name == "noop":
                run("corrected", "no op")
                expect(page.locator("#metrics")).to_contain_text("98 → 98")
                page.locator("#load-audit summary").click()
                expect(page.locator("#load-events")).to_contain_text("load no op")
                page.locator("#load-audit").evaluate("(e) => e.scrollIntoView({block: 'start'})")
                shot("06-noop")
            elif name == "roles":
                page.get_by_role("button", name="Sign out", exact=True).click()
                assert context.request.post(
                    args.origin + "/api/session",
                    headers={"Origin": args.origin},
                    data={"token": os.environ["WB_DEMO_ANALYST_TOKEN"]},
                ).ok
                page.reload()
                ready()
                expect(page.locator("#operations")).to_be_hidden()
                page.evaluate("window.scrollTo(0,0)")
                shot("07-analyst")
            elif name == "ai":
                live = json.loads(Path("docs/evidence/p05a/live.json").read_text())
                answer = live["answer"]
                body = (
                    "<p>Archived provider response from P05A · No new call in this recording.</p>"
                )
                for section in ("possible_causes", "missing_evidence", "suggested_next_checks"):
                    body += "<p><b>" + section.replace("_", " ").title() + "</b><br>"
                    body += "<br>".join(html.escape(n["text"]) for n in answer[section]) + "</p>"
                card(
                    chapter["title"],
                    body
                    + "<small>Broader P10 live evaluation and human review remain open.</small>",
                )
            elif name == "recovery":
                perf = json.loads(Path("docs/evidence/p11/performance.json").read_text())
                backup = json.loads(Path("docs/evidence/p11/backup-restore.json").read_text())
                assert backup["checkdb_passed"] and perf["identical_results"]
                card(
                    chapter["title"],
                    '<div class="row"><div class="box">Six abrupt exits<br>Audited recovery<br>'
                    "Actual restore + CHECKDB<br>Twelve matching table snapshots</div>"
                    '<div class="box">'
                    f"{perf['activities']:,} synthetic activities<br>Logical reads: "
                    f"{perf['median_logical_reads_before']:,} → "
                    f"{perf['median_logical_reads_after']}<br>"
                    f"{perf['read_reduction_percent']}% reduction<br>"
                    "Identical query results</div></div>"
                    "<p><small>Retained P11 measurements · Selected query only · "
                    "Not a production SLA</small></p>",
                )
            else:
                card(
                    chapter["title"],
                    "<ul><li>SQL reconciliation, provenance, permissions and audit</li>"
                    "<li>Recovery and actual restore proven; query tuning measured</li>"
                    "<li>Fresh Compose replay, screenshots, schema and runbooks</li>"
                    "<li>Open gate: broader live AI evaluation and human review</li></ul>"
                    "<p><small>github.com/BillMath2/data-reconciliation-workbench</small></p>",
                )
            if name in {"intro", "setup", "ai", "recovery", "close"}:
                page.screenshot(path=str(args.output / f"card-{name}.png"))
            start = time.monotonic() - epoch
            duration = max(30, sum(len(data) / 48000 + 0.25 for _, data in clips[name]) + 2)
            events.append(
                {
                    "id": name,
                    "title": chapter["title"],
                    "start": round(start, 3),
                    "duration": duration,
                    "narration": chapter["text"],
                }
            )
            print(f"CHAPTER {name}: {duration:.1f}s", flush=True)
            page.wait_for_timeout(100 if args.preview else duration * 1000)
        video = page.video
        elapsed = time.monotonic() - epoch
        assert not errors, errors
        context.close()
        raw = video.path()
        browser.close()
    result = {
        "mode": "live SQL browser recording",
        "preview": args.preview,
        "voice": story["voice_disclosure"],
        "elapsed_seconds": round(elapsed, 3),
        "chapters": events,
        "screenshots": screenshots,
        "passed": True,
        "ai_mode": "offline screen guidance; archived P05A live response shown separately",
    }
    (args.output / "recording.json").write_text(json.dumps(result, indent=2) + "\n", "utf-8")
    if args.preview:
        return
    render(args.output, raw, result, clips, args.ffmpeg)


if __name__ == "__main__":
    main()
