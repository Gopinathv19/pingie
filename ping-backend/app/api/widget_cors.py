"""CORS for the public widget API.

The dashboard's CORSMiddleware only knows the dashboard origins. The widget
runs on customers' sites, so its routes must answer any origin -- the route
itself then decides whether that origin is on the bot's allowed domains.
Credentials are never allowed cross-origin: the widget authenticates with a
conversation token header, not cookies.

This wraps the whole FastAPI app (main.py): it answers widget preflights
itself and adds the headers to widget responses on the way out. Everything
else passes straight through to the dashboard CORS handling.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_PREFIX = "/api/v1/widget"
_ALLOW_HEADERS = b"content-type, x-conversation-token"
_ALLOW_METHODS = b"GET, POST, OPTIONS"


class WidgetCORSMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(_PREFIX):
            await self.app(scope, receive, send)
            return
        origin = dict(scope["headers"]).get(b"origin")
        cors = [(b"vary", b"Origin")]
        if origin:
            cors += [
                (b"access-control-allow-origin", origin),
                (b"access-control-allow-methods", _ALLOW_METHODS),
                (b"access-control-allow-headers", _ALLOW_HEADERS),
                (b"access-control-max-age", b"600"),
            ]
        if scope["method"] == "OPTIONS":
            await send({"type": "http.response.start", "status": 204, "headers": cors})
            await send({"type": "http.response.body", "body": b""})
            return

        async def send_with_cors(message: Message) -> None:
            if message["type"] == "http.response.start":
                # Drop any CORS headers the dashboard middleware added.
                headers = [h for h in message.get("headers", []) if not h[0].lower().startswith(b"access-control-")]
                message = {**message, "headers": headers + cors}
            await send(message)

        await self.app(scope, receive, send_with_cors)
