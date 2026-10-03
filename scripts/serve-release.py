"""Serve only public release media locally, with HTTP range support for video seeking."""

from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.responses import FileResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]


async def transcript(request):
    return FileResponse(ROOT / "docs/release-narration.json", media_type="application/json")


app = Starlette(
    routes=[
        Route("/release-narration.json", transcript),
        Mount("/", app=StaticFiles(directory=ROOT / "docs/images/p12", html=True)),
    ]
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8020, log_level="warning")
