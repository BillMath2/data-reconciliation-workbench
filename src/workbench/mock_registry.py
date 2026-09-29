"""Read-only, deterministic project registry for the synthetic source demonstration."""

import argparse
import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query


def create_app(fixture_dir: Path) -> FastAPI:
    # Load once: a process serves one immutable fixture set throughout pagination.
    snapshots = {
        name: json.loads((fixture_dir / f"reference/projects-{name}.json").read_text("utf-8"))
        for name in ("default", "unknown-department")
    }
    app = FastAPI(title="Synthetic project registry", version="1.0.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "source": "project-registry", "synthetic": True}

    @app.get("/projects")
    def projects(
        cursor: str | None = None,
        scenario: str = Query(default="default"),
    ):
        if scenario not in {"default", "unknown-department", "incomplete"}:
            raise HTTPException(status_code=400, detail="Unknown synthetic scenario")
        offsets = {None: 0, "page-2": 10, "page-3": 20}
        if cursor not in offsets:
            raise HTTPException(status_code=400, detail="Invalid cursor")
        snapshot = snapshots[
            "unknown-department" if scenario == "unknown-department" else "default"
        ]
        offset = offsets[cursor]
        next_cursor = {0: "page-2", 10: "page-3", 20: None}[offset]
        if scenario == "incomplete":
            if offset == 20:
                raise HTTPException(status_code=503, detail="Synthetic missing final page")
            if offset == 10:
                next_cursor = None  # Fault injection: declares 25 but supplies only 20.
        return {
            **{key: value for key, value in snapshot.items() if key != "items"},
            "next_cursor": next_cursor,
            "items": snapshot["items"][offset : offset + 10],
        }

    return app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=Path("fixtures/generated"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args(argv)
    uvicorn.run(create_app(args.fixtures), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
