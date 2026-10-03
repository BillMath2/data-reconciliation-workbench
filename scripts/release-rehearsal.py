"""Replay a fresh Compose stack under an owned project; preserve the normal workbench."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env.workbench"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--ffmpeg", type=Path)
    args = parser.parse_args()
    if args.record and (not args.audio or not args.ffmpeg):
        parser.error("--record requires --audio and --ffmpeg")
    root, output = Path.cwd(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    values = dotenv_values(args.env_file, interpolate=False, encoding="utf-8-sig")
    if not all(values.get(k) for k in ("WB_DEMO_ANALYST_TOKEN", "WB_DEMO_OPERATOR_TOKEN")):
        parser.error("Initialize the dedicated demo configuration first")
    docker = shutil.which("docker")
    if not docker and os.name == "nt":
        docker = str(
            Path(os.environ["LOCALAPPDATA"]) / "Programs/DockerDesktop/resources/bin/docker.exe"
        )
    if not docker:
        parser.error("Docker CLI is required")
    project = "wb-p12-" + uuid4().hex[:12]
    env = {
        **os.environ,
        "WB_SQL_DATABASE": "workbench",
        "WB_AI_LIVE_ENABLED": "false",
        "OPENAI_API_KEY": "",
        "WB_BUILD_REVISION": "P12 local working tree",
    }
    env["PATH"] = str(Path(docker).parent) + os.pathsep + env.get("PATH", "")
    for key in ("WB_DEMO_ANALYST_TOKEN", "WB_DEMO_OPERATOR_TOKEN"):
        env[key] = values[key]
    override = output / "compose-override.yml"
    override.write_text(
        "services:\n  api:\n    command: [--container, --port, '8012']\n"
        "    ports: !override ['127.0.0.1:8012:8012']\n"
        '    healthcheck:\n      test: [CMD, python, -c, "import urllib.request; '
        "urllib.request.urlopen('http://127.0.0.1:8012/health', timeout=3)\"]\n"
        "  mock-registry:\n    ports: !override ['127.0.0.1:8013:8001']\n",
        "utf-8",
    )
    base = [
        docker,
        "compose",
        "--progress",
        "plain",
        "-p",
        project,
        "--env-file",
        str(args.env_file.resolve()),
        "-f",
        str(root / "docker-compose.yml"),
        "-f",
        str(override),
    ]
    manifest = {
        "project": project,
        "started_at": datetime.now(UTC).isoformat(),
        "mode": "fresh Compose project, network and SQL volume",
        "steps": [],
        "live_ai_enabled": False,
        "passed": False,
    }

    def save():
        (output / "rehearsal.json").write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")

    def run(name, command, database="workbench"):
        print("START " + name, flush=True)
        with (output / f"{name}.txt").open("w", encoding="utf-8") as log:
            result = subprocess.run(
                command,
                env={**env, "WB_SQL_DATABASE": database},
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        manifest["steps"].append({"name": name, "exit_code": result.returncode})
        save()
        if result.returncode:
            raise RuntimeError(f"{name} failed; inspect its local log")
        print("PASS " + name, flush=True)

    def compose(name, arguments, database="workbench"):
        run(name, base + arguments, database)

    def seed(database):
        compose(database + "-setup", ["--profile", "tools", "run", "--rm", "migrate"], database)
        compose(
            database + "-seed",
            ["--profile", "tools", "run", "--rm", "migrate", "seed-departments"],
            database,
        )
        reference = json.loads(Path("fixtures/generated/index.json").read_text())["reference_sets"][
            "default"
        ]
        compose(
            database + "-departments",
            ["run", "--rm", "workbench", "load-departments", "--reference-hash", reference],
            database,
        )
        compose(database + "-projects", ["run", "--rm", "workbench", "load-projects"], database)
        compose(
            database + "-api",
            ["--profile", "web", "up", "-d", "--build", "--wait", "--wait-timeout", "120", "api"],
            database,
        )

    succeeded = False
    save()
    try:
        compose("config", ["config", "--quiet"])
        compose("sql-ready", ["up", "-d", "--wait", "--wait-timeout", "240", "sqlserver"])
        compose("build", ["build", "workbench"])
        compose("setup", ["--profile", "tools", "run", "--build", "--rm", "migrate"])
        compose("setup-repeat", ["--profile", "tools", "run", "--rm", "migrate"])
        compose(
            "schema-export",
            [
                "--profile",
                "tools",
                "run",
                "--rm",
                "--entrypoint",
                "python",
                "--volume",
                f"{(root / 'scripts/export-schema.py').as_posix()}:/app/export-schema.py:ro",
                "--volume",
                f"{output.as_posix()}:/app/p12",
                "migrate",
                "/app/export-schema.py",
                "/app/p12/schema.json",
            ],
        )

        compose("health", ["run", "--rm", "workbench", "health"])
        compose("driver", ["run", "--rm", "workbench", "db-smoke"])
        compose(
            "registry", ["--profile", "sources", "up", "-d", "--build", "--wait", "mock-registry"]
        )
        compose("source-seed", ["--profile", "tools", "run", "--rm", "migrate", "seed-departments"])
        compose(
            "cli-demo",
            [
                "run",
                "--rm",
                "--volume",
                f"{output.as_posix()}:/app/p12",
                "workbench",
                "demo",
                "--output-dir",
                "/app/p12/cli-demo",
            ],
        )
        seed("workbench_ui")
        run(
            "browser-checks",
            [
                sys.executable,
                "scripts/check-ui.py",
                "--origin",
                "http://127.0.0.1:8012",
                "--output",
                str(output / "ui"),
            ],
        )
        if args.record:
            seed("workbench_preview")
            run(
                "recording-preview",
                [
                    sys.executable,
                    "scripts/record-release.py",
                    "--origin",
                    "http://127.0.0.1:8012",
                    "--output",
                    str(output / "preview"),
                    "--audio",
                    str(args.audio),
                    "--ffmpeg",
                    str(args.ffmpeg),
                    "--setup-evidence",
                    str(output),
                    "--preview",
                ],
            )
            seed("workbench_recording")
            run(
                "recording",
                [
                    sys.executable,
                    "scripts/record-release.py",
                    "--origin",
                    "http://127.0.0.1:8012",
                    "--output",
                    str(output / "recording"),
                    "--audio",
                    str(args.audio),
                    "--ffmpeg",
                    str(args.ffmpeg),
                    "--setup-evidence",
                    str(output),
                ],
            )
        succeeded = True
    finally:
        # The project name is generated locally above; never stop the default project.
        compose(
            "owned-stack-cleanup",
            [
                "--profile",
                "web",
                "--profile",
                "sources",
                "--profile",
                "tools",
                "--profile",
                "test",
                "down",
                "--volumes",
                "--remove-orphans",
            ],
        )
        manifest["passed"] = succeeded
        manifest["completed_at"] = datetime.now(UTC).isoformat()
        save()


if __name__ == "__main__":
    main()
