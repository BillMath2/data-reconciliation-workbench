"""Verify the running Compose API against the completed golden/correction/no-op demo."""

import json
import os
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

BASE = "http://127.0.0.1:8000"


def main():
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def request(path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Origin": BASE, "Content-Type": "application/json"} if data else {}
        with client.open(
            urllib.request.Request(BASE + path, data=data, headers=headers), timeout=10
        ) as response:
            return json.load(response)

    try:
        request("/api/loads")
    except urllib.error.HTTPError as error:
        assert error.code == 401
    else:
        raise AssertionError("Anonymous evidence access was allowed")
    login = request("/api/session", {"token": os.environ["WB_DEMO_ANALYST_TOKEN"]})
    assert login["role"] == "analyst"
    loads = request("/api/loads?business_date=2026-09-25")["items"]
    golden = next(item for item in loads if item["status"] == "superseded")
    corrected = next(item for item in loads if item["is_current"])
    repeated = next(item for item in loads if item["status"] == "no_op")
    original = request(f"/api/loads/{golden['load_id']}/reconciliation")
    current = request(f"/api/loads/{corrected['load_id']}/reconciliation")
    assert original["summary"]["source_completed_count"] == 100
    assert original["summary"]["curated_completed_count"] == 94
    assert current["summary"]["curated_completed_count"] == 98
    assert request(f"/api/loads/{repeated['load_id']}/evidence") == current["packet"]
    findings = request(f"/api/exceptions?load_id={golden['load_id']}&status=all")["items"]
    assert len(findings) == 6 and all(item["status"] == "resolved" for item in findings)
    detail = request(f"/api/exceptions/{findings[0]['exception_id']}")
    assert detail["resolved_by_load_id"] == corrected["load_id"]
    assert detail["untrusted_source"] and detail["rule_definition"]
    print(
        json.dumps(
            {
                "status": "ok",
                "check": "evidence-api",
                "historical_count": 94,
                "corrected_count": 98,
                "resolved_findings": 6,
            }
        )
    )


if __name__ == "__main__":
    main()
