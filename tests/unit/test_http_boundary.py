import asyncio

import pytest
from starlette.responses import JSONResponse

from workbench.http_boundary import DemoBoundary

ORIGIN = "http://127.0.0.1:8000"


def request(chunks, *, length=None, extra=(), disconnected=False):
    """Call ASGI directly so a client cannot repair deliberately false length headers."""
    called, sent = [], []
    headers = [
        (b"host", b"127.0.0.1:8000"),
        (b"origin", ORIGIN.encode()),
        (b"content-type", b"application/json"),
        (b"content-length", str(sum(map(len, chunks)) if length is None else length).encode()),
    ]
    headers.extend(extra)
    scope = {"type": "http", "method": "POST", "path": "/api/activity-runs", "headers": headers}

    async def run():
        messages = iter(
            [
                {"type": "http.request", "body": chunk, "more_body": i < len(chunks) - 1}
                for i, chunk in enumerate(chunks)
            ]
        )

        async def receive():
            return {"type": "http.disconnect"} if disconnected else next(messages)

        async def send(message):
            sent.append(message)

        async def downstream(scope, receive, send):
            called.append((await receive())["body"])
            await JSONResponse({"ok": True})(scope, receive, send)

        await DemoBoundary(downstream, origin=ORIGIN)(scope, receive, send)

    asyncio.run(run())
    return called, sent


@pytest.mark.parametrize(
    "chunks,length,status",
    [
        ([b"{}"], 1, 400),
        ([b"{}"], 5, 400),
        ([b"x" * 4096, b"x" * 4097], 2, 413),
        ([b"{}"], "-2", 413),
        ([b"{}"], "8193", 413),
    ],
)
def test_actual_bytes_and_declaration_checked_before_application(chunks, length, status):
    called, sent = request(chunks, length=length)
    assert not called
    assert sent[0]["status"] == status
    assert dict(sent[0]["headers"])[b"cache-control"] == b"no-store"


@pytest.mark.parametrize(
    "header,value,status",
    [
        (b"host", b"evil.example", 400),
        (b"origin", ORIGIN.encode(), 403),
        (b"content-type", b"text/plain", 415),
        (b"content-length", b"2", 413),
        (b"transfer-encoding", b"chunked", 413),
    ],
)
def test_ambiguous_write_headers_never_reach_application(header, value, status):
    called, sent = request([b"{}"], extra=[(header, value)])
    assert not called and sent[0]["status"] == status


def test_valid_split_body_replayed_once_and_disconnect_does_not_write():
    called, sent = request([b'{"reason":', b'"review"}'])
    assert called == [b'{"reason":"review"}'] and sent[0]["status"] == 200
    called, sent = request([b"{}"], disconnected=True)
    assert not called and not sent
