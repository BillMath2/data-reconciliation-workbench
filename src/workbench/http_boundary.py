"""Local-demo HTTP boundary, including an actual byte limit before JSON parsing."""

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

MAX_BODY = 8192
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self'; connect-src 'self'; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    ),
}


class DemoBoundary:
    def __init__(self, app, *, origin):
        self.app = app
        self.origin = origin

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def protected_send(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.update(SECURITY_HEADERS)
            await send(message)

        async def reject(status, message):
            await JSONResponse({"detail": message}, status_code=status)(
                scope, receive, protected_send
            )

        headers = Headers(scope=scope)
        if headers.getlist("host") != [self.origin.split("//", 1)[1]]:
            return await reject(400, "Invalid demo host.")
        if scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            return await self.app(scope, receive, protected_send)
        if headers.getlist("origin") != [self.origin]:
            return await reject(403, "Same-origin writes are required.")
        types = headers.getlist("content-type")
        if len(types) != 1 or types[0].split(";", 1)[0] != "application/json":
            return await reject(415, "JSON writes are required.")
        lengths = headers.getlist("content-length")
        if (
            len(lengths) != 1
            or not lengths[0].isascii()
            or not lengths[0].isdecimal()
            or len(lengths[0]) > 4
            or int(lengths[0]) > MAX_BODY
            or "transfer-encoding" in headers
        ):
            return await reject(413, "A bounded request body is required.")
        declared = int(lengths[0])
        content = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(content) + len(chunk) > MAX_BODY:
                return await reject(413, "Request body exceeds the demo limit.")
            content.extend(chunk)
            if not message.get("more_body", False):
                break
        if len(content) != declared:
            return await reject(400, "Request body length does not match its declaration.")

        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(content), "more_body": False}

        await self.app(scope, bounded_receive, protected_send)
