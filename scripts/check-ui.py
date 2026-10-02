"""Exercise the real screen; --fixture substitutes an explicitly simulated service for SQL."""

import argparse
import json
import os
import secrets
import sys
import threading
import time
from pathlib import Path

import uvicorn
from PIL import Image
from playwright.sync_api import expect, sync_playwright

from workbench.api import create_app


def journey(origin, analyst, operator, output, fixture):
    output.mkdir(parents=True, exist_ok=True)
    captures = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1200})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_default_timeout(30000)

        def ready():
            expect(page.locator("#workbench")).to_have_attribute("aria-busy", "false")

        def capture(name):
            ready()
            page.evaluate("window.scrollTo(0,0)")
            path = output / f"{name}.png"
            page.screenshot(path=str(path), full_page=True)
            captures.append(path)

        def sign_in(token):
            page.locator("#token").fill(token)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator("#workbench")).to_be_visible()
            ready()

        def run(snapshot, expected):
            page.locator("#snapshot").select_option(snapshot)
            page.locator("#run-reason").fill("Reviewed supplied source snapshot")
            page.get_by_role("button", name="Run snapshot", exact=True).click()
            expect(page.locator("#run-result")).to_contain_text(expected)
            ready()

        page.goto(origin)
        sign_in(operator)
        expect(page.locator("#operations")).to_be_visible()
        # Refuse to run a demonstration over an existing activity history.
        if page.request.get(origin + "/api/loads?limit=1").json()["items"]:
            raise RuntimeError(
                "Browser walkthrough requires an isolated database with no activities."
            )
        expect(page.locator("#report-state")).to_contain_text("No saved reconciliation")
        run("golden", "published with exceptions")
        expect(page.locator("#metrics")).to_contain_text("100 → 94")
        expect(page.locator("#metrics")).to_contain_text("202 → 189")
        expect(page.locator("#exceptions tr")).to_have_count(6)
        golden = page.locator("#load").input_value()
        page.locator("#load-audit summary").click()
        expect(page.locator("#load-actor")).to_contain_text("demo-operator")
        expect(page.locator("#load-events")).to_contain_text("Reviewed supplied source snapshot")
        expect(page.locator("#load-events")).to_contain_text("load published")
        page.locator("#load-audit summary").click()
        page.locator("#exceptions button").first.click()
        expect(page.locator("#detail-state")).to_contain_text("OPEN")
        ready()
        finding = page.locator("#evidence-id").inner_text().split(":")[1]
        original_source = page.locator("#source").inner_text()
        capture("01-golden")
        page.locator("#ack-reason").fill("Reviewed captured source with source owner")
        page.get_by_role("button", name="Acknowledge finding", exact=True).click()
        expect(page.locator("#detail-state")).to_contain_text("ACKNOWLEDGED")
        ready()
        expect(page.locator("#resolution")).to_contain_text("Still unresolved")
        # Persisted operator prose is untrusted too, not just source rows.
        reviewed = page.request.get(origin + f"/api/exceptions/{finding}").json()
        assert reviewed["acknowledged_by"] == "demo-operator"
        capture("02-reviewed")
        run("corrected", "published ·")
        expect(page.locator("#metrics")).to_contain_text("98 → 98")
        expect(page.locator("#metrics")).to_contain_text("197 → 197")
        expect(page.locator("#exceptions tr")).to_have_count(0)
        corrected = page.locator("#load").input_value()
        capture("03-corrected")
        page.locator("#scope").select_option("date")
        ready()
        page.locator("#status").select_option("resolved")
        expect(page.locator("#exceptions tr")).to_have_count(6)
        ready()
        page.locator(f'#exceptions tr[data-id="{finding}"] button').click()
        expect(page.locator("#detail-state")).to_contain_text("RESOLVED")
        expect(page.locator("#source")).to_have_text(original_source)
        expect(page.locator("#resolution")).to_contain_text(corrected)
        capture("04-resolved")
        run("corrected", "no op")
        expect(page.locator("#report-state")).to_contain_text("no op")
        expect(page.locator("#metrics")).to_contain_text("98 → 98")
        attempt = page.locator("#load").input_value()
        audit = page.request.get(origin + f"/api/loads/{attempt}/audit").json()
        assert audit["load"]["load_id"] == attempt
        assert [e["action"] for e in audit["items"]] == ["load_started", "load_no_op"]
        capture("05-rerun")
        # Replaying superseded input is not undo: report shows historical evidence.
        run("golden", "no op")
        expect(page.locator("#publication")).to_have_text("Historical publication")
        expect(page.locator("#metrics")).to_contain_text("100 → 94")
        current = page.request.get(origin + "/api/loads").json()["items"]
        assert next(row for row in current if row["is_current"])["load_id"] == corrected
        page.locator("#load").select_option(golden)
        ready()
        expect(page.locator("#publication")).to_have_text("Historical publication")
        page.get_by_role("button", name="Sign out", exact=True).click()
        expect(page.locator("#login-panel")).to_be_visible()
        sign_in(analyst)
        expect(page.locator("#operations")).to_be_hidden()
        session = page.request.get(origin + "/api/session").json()
        denied = page.request.post(
            origin + "/api/activity-runs",
            headers={"Origin": origin, "X-CSRF-Token": session["csrf_token"]},
            data={"snapshot": "corrected", "business_date": "2026-09-25", "reason": "Denied test"},
        )
        assert denied.status == 403
        denied_ack = page.request.post(
            origin + f"/api/exceptions/{finding}/acknowledge",
            headers={"Origin": origin, "X-CSRF-Token": session["csrf_token"]},
            data={"reason": "Analyst cannot write"},
        )
        assert denied_ack.status == 403
        # A real browser form from another origin cannot initiate a write.
        attacker = context.new_page()
        attacker.route(
            "http://localhost:8018/",
            lambda route: route.fulfill(
                content_type="text/html",
                body='<form method="post" action="'
                + origin
                + '/api/activity-runs"><input name="snapshot" value="corrected">'
                '<button type="submit">Submit cross-origin form</button></form>',
            ),
        )
        attacker.goto("http://localhost:8018/")
        with attacker.expect_response(origin + "/api/activity-runs") as rejected:
            attacker.get_by_role("button", name="Submit cross-origin form").click()
        assert rejected.value.status == 403
        attacker.close()
        assert page.request.get(origin + "/api/session").json()["role"] == "analyst"
        page.locator("#business-date").fill("2026-09-24")
        page.locator("#business-date").dispatch_event("change")
        expect(page.locator("#freshness")).to_have_text("Feed overdue")
        ready()
        expect(page.locator("#exceptions tr")).to_have_count(0)
        expect(page.locator("#metrics")).to_be_empty()
        capture("06-missing-date")
        # Browser-level escaping, partial metrics, and failed refresh presentation.
        page.locator("#business-date").fill("2026-09-25")
        page.locator("#business-date").dispatch_event("change")
        ready()
        page.locator("#scope").select_option("date")
        ready()
        page.locator("#status").select_option("all")
        expect(page.locator("#exceptions tr")).to_have_count(6)
        ready()
        detail_url = origin + f"/api/exceptions/{finding}"
        detail = page.request.get(detail_url).json()
        detail["untrusted_source"] = {"notes": '<img src=x onerror="window.pwned=true">'}
        payload = '<svg onload="window.pwned=true"></svg>'
        detail["untrusted_evidence"] = {"value": payload}
        detail["rule_definition"] = {"description": payload}
        detail["events"] = [{"actor": payload, "detail": {"reason": payload}}]
        detail["resolution_reason"] = payload
        page.route(detail_url, lambda route: route.fulfill(json=detail))
        page.locator(f'#exceptions tr[data-id="{finding}"] button').click()
        expect(page.locator("#source")).to_contain_text("<img")
        assert page.locator("#source img").count() == 0
        for field in ("evidence", "rule", "audit", "resolution"):
            assert "<svg" in page.locator("#" + field).text_content()
            assert page.locator("#" + field + " svg").count() == 0
        assert page.evaluate("window.pwned === undefined")
        page.unroute(detail_url)
        ready()
        page.locator(f'#exceptions tr[data-id="{finding}"] button').click()
        expect(page.locator("#source")).to_have_text(original_source)
        ready()
        page.set_viewport_size({"width": 390, "height": 844})
        capture("07-mobile")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), page.evaluate(
            "Array.from(document.querySelectorAll('body *')).filter(e => "
            "e.getBoundingClientRect().right > innerWidth).map(e => e.tagName + '#' + e.id)"
        )
        page.set_viewport_size({"width": 1440, "height": 1200})
        page.locator("#load-audit summary").click()
        capture("08-load-audit")
        page.locator("#load-audit summary").click()
        # Audit display escapes operator-authored reasons and supports bounded pages.
        selected = page.locator("#load").input_value()
        audit_url = origin + f"/api/loads/{selected}/audit?limit=25&offset=0"
        audit = page.request.get(audit_url).json()
        audit["items"] = [audit["items"][0]] * 25
        audit["items"][0]["detail"] = {"reason": payload}
        page.route(
            "**/audit?*",
            lambda route: route.fulfill(
                json={**audit, "items": [] if "offset=25" in route.request.url else audit["items"]}
            ),
        )
        page.get_by_role("button", name="Refresh", exact=True).click()
        ready()
        page.locator("#load-audit summary").click()
        expect(page.locator("#load-events")).to_contain_text("<svg")
        assert page.locator("#load-events svg").count() == 0
        page.get_by_role("button", name="Next events", exact=True).click()
        ready()
        expect(page.locator("#load-events")).to_be_empty()
        page.get_by_role("button", name="Previous events", exact=True).click()
        ready()
        expect(page.locator("#load-events li")).to_have_count(25)
        assert page.evaluate("window.pwned === undefined")
        page.unroute("**/audit?*")
        page.locator("#load-audit summary").click()
        # Exercise states not present in the successful correction scenario.
        selected = page.locator("#load").input_value()
        report_url = origin + f"/api/loads/{selected}/reconciliation"
        report = page.request.get(report_url).json()
        report["summary"].update(
            {
                "source_completed_units": None,
                "source_units_complete": False,
                "unknown_unit_rows": 1,
                "source_status_complete": False,
                "unknown_status_rows": 1,
            }
        )
        page.route(report_url, lambda route: route.fulfill(json=report))
        feed_url = origin + "/api/freshness?business_date=2026-09-25"
        feed = page.request.get(feed_url).json()
        feed["failed_refresh"] = True
        page.route(feed_url, lambda route: route.fulfill(json=feed))
        page.get_by_role("button", name="Refresh", exact=True).click()
        expect(page.locator("#freshness")).to_have_text("Failed refresh")
        expect(page.locator("#metrics")).to_contain_text("Unknown")
        expect(page.locator("#accounting")).to_contain_text("completed count is incomplete")
        ready()
        page.unroute(report_url)
        page.unroute(feed_url)
        # A failed load must not leave another load's summary on screen.
        page.route(
            report_url,
            lambda route: route.fulfill(status=404, json={"detail": "No saved reconciliation"}),
        )
        page.get_by_role("button", name="Refresh", exact=True).click()
        expect(page.locator("#report-state")).to_contain_text("no saved reconciliation")
        ready()
        expect(page.locator("#metrics")).to_be_empty()
        page.unroute(report_url)
        # Pagination must request the next slice, even when it is empty.
        findings = page.request.get(
            origin + "/api/exceptions?business_date=2026-09-25&status=all"
        ).json()
        entries = [findings["items"][0]] * 25
        page.route(
            "**/api/exceptions?*",
            lambda route: route.fulfill(
                json={"items": [] if "offset=25" in route.request.url else entries}
            ),
        )
        page.get_by_role("button", name="Refresh", exact=True).click()
        expect(page.locator("#exceptions tr")).to_have_count(25)
        ready()
        page.get_by_role("button", name="Next findings", exact=True).click()
        expect(page.locator("#exceptions tr")).to_have_count(0)
        ready()
        expect(page.get_by_role("button", name="Previous findings", exact=True)).to_be_enabled()
        page.get_by_role("button", name="Previous findings", exact=True).click()
        expect(page.locator("#exceptions tr")).to_have_count(25)
        ready()
        page.unroute("**/api/exceptions?*")
        page.route(
            "**/api/loads?*",
            lambda route: route.fulfill(
                status=503,
                json={"detail": "Evidence service unavailable; check database readiness."},
            ),
        )
        page.get_by_role("button", name="Refresh", exact=True).click()
        expect(page.locator("#notice")).to_contain_text("Evidence service unavailable")
        ready()
        expect(page.locator("#metrics")).to_be_empty()
        page.unroute("**/api/loads?*")
        page.route(
            "**/api/loads?*",
            lambda route: route.fulfill(
                status=401, json={"detail": "A local demo session is required."}
            ),
        )
        page.get_by_role("button", name="Refresh", exact=True).click()
        expect(page.locator("#login-panel")).to_be_visible()
        expect(page.locator("#workbench")).to_be_hidden()
        assert not errors, errors
        context.close()
        browser.close()

    # A paced replay of actual screenshots, not continuous screen video.
    images = []
    for path in captures[:5]:
        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail((1200, 1200))
            canvas = Image.new("RGB", (1200, 1200), "#f3f5f4")
            canvas.paste(image, (0, 0))
            images.append(canvas)
    images[0].save(
        output / "walkthrough.gif", save_all=True, append_images=images[1:], duration=5000, loop=0
    )
    (output / "verification.json").write_text(
        json.dumps(
            {
                "mode": "browser fixture; simulated lifecycle, no SQL"
                if fixture
                else "live SQL API",
                "revision": os.environ.get("GITHUB_SHA", "local working tree"),
                "captures": [p.name for p in captures],
                "passed": True,
                "checks": [
                    "inspect",
                    "acknowledge",
                    "correct",
                    "resolve",
                    "no-op",
                    "historical replay",
                    "analyst denial",
                    "missing date",
                    "escaping",
                    "mobile",
                    "service error",
                    "partial totals",
                    "failed refresh",
                    "unavailable report",
                    "exception pagination",
                    "load audit",
                    "audit pagination",
                    "audit escaping",
                    "analyst acknowledgement denial",
                    "cross-origin browser form",
                    "expiry",
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Browser walkthrough passed (" + ("simulated fixture" if fixture else "live SQL") + ").")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--origin", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=Path("runs/ui"))
    args = parser.parse_args()
    server = thread = None
    analyst, operator = (
        os.environ.get("WB_DEMO_ANALYST_TOKEN"),
        os.environ.get("WB_DEMO_OPERATOR_TOKEN"),
    )
    if args.fixture:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests/e2e"))
        from fixture_service import FixtureService

        analyst, operator = secrets.token_hex(24), secrets.token_hex(24)
        app = create_app(None, analyst_token=analyst, operator_token=operator, origin=args.origin)
        app.state.evidence = app.state.operations = FixtureService()
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=int(args.origin.rsplit(":", 1)[1]),
                log_level="error",
                access_log=False,
            )
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not server.started:
            raise RuntimeError("Browser fixture server did not start.")
    elif not analyst or not operator:
        parser.error("Live mode requires both WB_DEMO_*_TOKEN environment variables.")
    try:
        journey(args.origin, analyst, operator, args.output, args.fixture)
    finally:
        if server:
            server.should_exit = True
            thread.join(timeout=10)


if __name__ == "__main__":
    main()
