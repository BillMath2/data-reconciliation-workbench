"""Bounded demo source selection; no caller-controlled paths, SQL, or registry URLs."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

from workbench import freshness, pipeline
from workbench.validation import LoadError

FIXTURES = Path("fixtures/generated/activity")
SNAPSHOTS = {"golden": "Golden source · known discrepancies", "corrected": "Corrected source"}


class OperationsService:
    def __init__(self, settings):
        self.settings = settings

    def snapshots(self):
        return {
            "items": [
                {
                    "id": name,
                    "label": label,
                    "business_date": json.loads(
                        (FIXTURES / f"{name}.manifest.json").read_text(encoding="utf-8")
                    )["business_date"],
                }
                for name, label in SNAPSHOTS.items()
            ]
        }

    def freshness(self, business_date):
        return freshness.inspect(self.settings, business_date, datetime.now(UTC))

    def run(self, snapshot, business_date, actor, reason):
        if snapshot not in SNAPSHOTS:
            raise LoadError("INVALID_REQUEST", "Select a supported demo snapshot.")
        selected = next(s for s in self.snapshots()["items"] if s["id"] == snapshot)
        if date.fromisoformat(selected["business_date"]) != date.fromisoformat(business_date):
            raise LoadError(
                "INVALID_REQUEST", "Snapshot does not match the selected business date."
            )
        return pipeline.load_activities(
            self.settings,
            FIXTURES / f"{snapshot}.csv",
            FIXTURES / f"{snapshot}.manifest.json",
            actor=actor,
            reason=reason,
        )
