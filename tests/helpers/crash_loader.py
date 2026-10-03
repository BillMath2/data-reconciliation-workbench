"""Test-only worker: ungraceful exit skips Python cleanup and SQL rollback handlers."""

import os
import sys
from pathlib import Path

from workbench.config import load_settings
from workbench.pipeline import ingest, load_activities

point = sys.argv[1]


def crash(stage):
    if stage == point:
        print("Interrupted at " + stage, flush=True)
        os._exit(23)


if point == "started":

    def capture(_):
        crash("started")

    ingest(load_settings(), "daily-activity", capture, actor="crash-rehearsal")
else:
    load_activities(
        load_settings(),
        Path("fixtures/generated/activity/corrected.csv"),
        Path("fixtures/generated/activity/corrected.manifest.json"),
        actor="crash-rehearsal",
        fault=crash,
    )
raise SystemExit("Fault point was not reached")
