"""Local demo evidence API with server-side identities and session-bound writes."""

import argparse
import os
import re
import secrets
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal
from uuid import UUID

import uvicorn
from dotenv import dotenv_values
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from workbench.config import ConfigurationError, load_settings
from workbench.evidence import EvidenceService
from workbench.http_boundary import DemoBoundary
from workbench.investigations import InvestigationService
from workbench.operations import OperationsService
from workbench.validation import LoadError

COOKIE = "workbench_session"
SESSION_SECONDS = 3600


@dataclass(frozen=True)
class Identity:
    actor: str
    role: str
    csrf: str
    expires: float


class Sessions:
    def __init__(self, analyst_token, operator_token):
        if (
            any(
                not isinstance(t, str) or not re.fullmatch(r"[A-Za-z0-9_+!/=.-]{32,128}", t)
                for t in (analyst_token, operator_token)
            )
            or analyst_token == operator_token
        ):
            raise ConfigurationError("Configure distinct 32-128 character demo access tokens.")
        self.tokens = {"analyst": analyst_token, "operator": operator_token}
        self.values = {}
        self.lock = Lock()

    def login(self, token, old_session=None):
        role = next(
            (
                role
                for role, expected in self.tokens.items()
                if secrets.compare_digest(token, expected)
            ),
            None,
        )
        if role is None:
            raise HTTPException(401, "Invalid demo credential.")
        with self.lock:
            self.values = {k: v for k, v in self.values.items() if v.expires > time.monotonic()}
            self.values.pop(old_session, None)
            if len(self.values) >= 256:
                raise HTTPException(503, "Demo session capacity reached.")
            session_id = secrets.token_urlsafe(32)
            identity = Identity(
                f"demo-{role}", role, secrets.token_urlsafe(32), time.monotonic() + SESSION_SECONDS
            )
            self.values[session_id] = identity
        return session_id, identity

    def get(self, session_id):
        with self.lock:
            identity = self.values.get(session_id)
            if identity is None or identity.expires <= time.monotonic():
                self.values.pop(session_id, None)
                raise HTTPException(401, "A local demo session is required.")
            return identity

    def logout(self, session_id):
        with self.lock:
            self.values.pop(session_id, None)


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    token: str = Field(min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_+!/=.-]+$")


class Acknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    reason: str = Field(min_length=1, max_length=500)


class ActivityRun(Acknowledgement):
    snapshot: Literal["golden", "corrected"]
    business_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    load_id: UUID
    exception_id: UUID | None = None
    provider: Literal["off", "stub", "openai"] = "stub"


def identity(request: Request):
    return request.app.state.sessions.get(request.cookies.get(COOKIE))


def writer(request: Request, user: Annotated[Identity, Depends(identity)]):
    token = request.headers.get("x-csrf-token", "")
    if not secrets.compare_digest(token.encode(), user.csrf.encode()):
        raise HTTPException(403, "Invalid CSRF token.")
    return user


def operator(user: Annotated[Identity, Depends(writer)]):
    if user.role != "operator":
        raise HTTPException(403, "Operator role required.")
    return user


def service(request: Request):
    return request.app.state.evidence


def operations(request: Request):
    return request.app.state.operations


def invoke(method, *args, **kwargs):
    try:
        return method(*args, **kwargs)
    except LoadError as error:
        status = {
            "NOT_FOUND": 404,
            "REPORT_UNAVAILABLE": 404,
            "ALREADY_RESOLVED": 409,
            "WORKER_BUSY": 409,
        }.get(error.code, 422)
        raise HTTPException(status, str(error)) from None
    except Exception:
        # Do not pass driver messages or connection values into HTTP output or server traces.
        raise HTTPException(
            503, "Evidence service unavailable; check database readiness."
        ) from None


def create_app(
    settings,
    *,
    analyst_token,
    operator_token,
    origin="http://127.0.0.1:8000",
    ai_key=None,
    ai_live_enabled=False,
):
    if not re.fullmatch(r"http://(127\.0\.0\.1|localhost):[0-9]{1,5}", origin):
        raise ConfigurationError("The demo origin must be an explicit localhost HTTP port.")
    app = FastAPI(
        title="Data Reconciliation Workbench (local demo)",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.sessions = Sessions(analyst_token, operator_token)
    app.state.evidence = EvidenceService(settings)
    app.state.operations = OperationsService(settings)
    app.state.investigations = InvestigationService(
        settings, key=ai_key, live_enabled=ai_live_enabled
    )
    assets = Path(__file__).with_name("static")
    app.mount("/static", StaticFiles(directory=assets), name="static")

    @app.get("/", include_in_schema=False)
    def screen():
        return FileResponse(assets / "index.html")

    app.add_middleware(DemoBoundary, origin=origin)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # Default validation details can echo the login credential or arbitrary source input.
        return JSONResponse({"detail": "Invalid request fields."}, status_code=422)

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "local-demo", "database_checked": False}

    @app.post("/api/session")
    def login(body: Login, request: Request, response: Response):
        session_id, user = app.state.sessions.login(body.token, request.cookies.get(COOKIE))
        response.set_cookie(
            COOKIE,
            session_id,
            max_age=SESSION_SECONDS,
            httponly=True,
            samesite="strict",
            secure=False,
            path="/",
        )
        return {
            "actor": user.actor,
            "role": user.role,
            "csrf_token": user.csrf,
            "mode": "local-demo",
        }

    @app.get("/api/session")
    def whoami(user: Annotated[Identity, Depends(identity)]):
        return {
            "actor": user.actor,
            "role": user.role,
            "csrf_token": user.csrf,
            "mode": "local-demo",
        }

    @app.post("/api/session/logout")
    def logout(request: Request, response: Response, user: Annotated[Identity, Depends(writer)]):
        app.state.sessions.logout(request.cookies.get(COOKIE))
        response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")
        return {"status": "signed_out"}

    reader = [Depends(identity)]

    @app.get("/api/investigations/capabilities", dependencies=reader)
    def investigation_capabilities():
        return app.state.investigations.capabilities()

    @app.post("/api/investigations")
    def investigate(body: InvestigationRequest, user: Annotated[Identity, Depends(writer)]):
        return invoke(
            app.state.investigations.create,
            app.state.evidence,
            app.state.operations,
            str(body.load_id),
            str(body.exception_id) if body.exception_id else None,
            body.provider,
            user.actor,
        )

    @app.get("/api/investigations", dependencies=reader)
    def investigation_history(
        load_id: UUID, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)
    ):
        return invoke(app.state.investigations.list, str(load_id), limit, offset)

    @app.get("/api/investigations/{investigation_id}", dependencies=reader)
    def saved_investigation(investigation_id: UUID):
        return invoke(app.state.investigations.get, str(investigation_id))

    @app.get("/api/investigations/{investigation_id}/evidence/{evidence_id}", dependencies=reader)
    def investigation_citation(investigation_id: UUID, evidence_id: str):
        return invoke(app.state.investigations.citation, str(investigation_id), evidence_id)

    @app.get("/api/snapshots", dependencies=reader)
    def snapshots(svc: Annotated[OperationsService, Depends(operations)]):
        return invoke(svc.snapshots)

    @app.get("/api/freshness", dependencies=reader)
    def feed_state(business_date: date, svc: Annotated[OperationsService, Depends(operations)]):
        return invoke(svc.freshness, business_date)

    @app.post("/api/activity-runs")
    def activity_run(
        body: ActivityRun,
        user: Annotated[Identity, Depends(operator)],
        svc: Annotated[OperationsService, Depends(operations)],
    ):
        try:
            date.fromisoformat(body.business_date)
        except ValueError:
            raise HTTPException(422, "Invalid business date.") from None
        return invoke(svc.run, body.snapshot, body.business_date, user.actor, body.reason)

    @app.get("/api/loads", dependencies=reader)
    def loads(
        svc: Annotated[EvidenceService, Depends(service)],
        business_date: date | None = None,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0, le=100000),
    ):
        return invoke(svc.loads, business_date, limit, offset)

    @app.get("/api/loads/{load_id}/reconciliation", dependencies=reader)
    def report(load_id: UUID, svc: Annotated[EvidenceService, Depends(service)]):
        return invoke(svc.report, str(load_id))

    @app.get("/api/loads/{load_id}/audit", dependencies=reader)
    def load_audit(
        load_id: UUID,
        svc: Annotated[EvidenceService, Depends(service)],
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0, le=100000),
    ):
        return invoke(svc.audit, str(load_id), limit, offset)

    @app.get("/api/loads/{load_id}/evidence", dependencies=reader)
    def packet(load_id: UUID, svc: Annotated[EvidenceService, Depends(service)]):
        return invoke(svc.packet, str(load_id))

    @app.get("/api/loads/{load_id}/evidence/{evidence_id}", dependencies=reader)
    def citation(
        load_id: UUID, evidence_id: str, svc: Annotated[EvidenceService, Depends(service)]
    ):
        return invoke(svc.citation, str(load_id), evidence_id)

    @app.get("/api/exceptions", dependencies=reader)
    def exceptions(
        svc: Annotated[EvidenceService, Depends(service)],
        load_id: UUID | None = None,
        business_date: date | None = None,
        status: Literal["all", "unresolved", "open", "acknowledged", "resolved"] = "unresolved",
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0, le=100000),
    ):
        return invoke(
            svc.exceptions, str(load_id) if load_id else None, business_date, status, limit, offset
        )

    @app.get("/api/exceptions/{exception_id}", dependencies=reader)
    def exception(exception_id: UUID, svc: Annotated[EvidenceService, Depends(service)]):
        return invoke(svc.exception, str(exception_id))

    @app.post("/api/exceptions/{exception_id}/acknowledge")
    def acknowledge(
        exception_id: UUID,
        body: Acknowledgement,
        user: Annotated[Identity, Depends(operator)],
        svc: Annotated[EvidenceService, Depends(service)],
    ):
        return invoke(svc.acknowledge, str(exception_id), user.actor, body.reason)

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--container", action="store_true", help="Bind within Compose; publish only on localhost"
    )
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.port <= 65535:
            raise ConfigurationError("Port must be between 1 and 65535.")
        settings = load_settings(args.env_file)
        if settings.username.lower() != "workbench_app":
            raise ConfigurationError("The API requires the restricted workbench_app SQL login.")
        values = {
            **(dotenv_values(args.env_file, interpolate=False) if args.env_file else {}),
            **os.environ,
        }
        app = create_app(
            settings,
            analyst_token=values.get("WB_DEMO_ANALYST_TOKEN"),
            operator_token=values.get("WB_DEMO_OPERATOR_TOKEN"),
            origin=f"http://127.0.0.1:{args.port}",
            ai_key=values.get("OPENAI_API_KEY"),
            ai_live_enabled=values.get("WB_AI_LIVE_ENABLED", "false").lower() == "true",
        )
    except (ConfigurationError, OSError, UnicodeError) as error:
        message = (
            str(error)
            if isinstance(error, ConfigurationError)
            else "Demo configuration unavailable."
        )
        parser.exit(2, message + "\n")
    uvicorn.run(
        app,
        host="0.0.0.0" if args.container else "127.0.0.1",
        port=args.port,
        workers=1,
        proxy_headers=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
