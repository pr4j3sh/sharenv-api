"""ASGI middleware: bounded bodies, JSON depth guard, and response headers."""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from fastapi import FastAPI
from starlette.responses import JSONResponse

from app.core.config import settings

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


def _header_values(raw_headers: list[tuple[bytes, bytes]], name: bytes) -> list[bytes]:
    target = name.lower()
    return [value for key, value in raw_headers if key.lower() == target]


def _first_header(raw_headers: list[tuple[bytes, bytes]], name: bytes) -> bytes | None:
    values = _header_values(raw_headers, name)
    return values[0] if values else None


def _remove_header(raw_headers: list[tuple[bytes, bytes]], name: bytes) -> list[tuple[bytes, bytes]]:
    target = name.lower()
    return [(key, value) for key, value in raw_headers if key.lower() != target]


def _set_header(
    raw_headers: list[tuple[bytes, bytes]], name: bytes, value: bytes
) -> list[tuple[bytes, bytes]]:
    return [*_remove_header(raw_headers, name), (name.lower(), value)]


def _parse_int_header(value: bytes | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.decode("ascii").strip())
    except (ValueError, UnicodeDecodeError):
        return -1


def _content_type_is_json(value: bytes | None) -> bool:
    if value is None:
        return False
    raw = value.decode("latin-1").split(";", 1)[0].strip().lower()
    return raw == "application/json" or raw.endswith("+json")


def _json_within_limits(
    value: Any,
    *,
    depth: int,
    nodes: list[int],
    max_depth: int,
    max_nodes: int,
) -> bool:
    if depth > max_depth:
        return False

    nodes[0] += 1
    if nodes[0] > max_nodes:
        return False

    if isinstance(value, dict):
        for item in value.values():
            if not _json_within_limits(
                item,
                depth=depth + 1,
                nodes=nodes,
                max_depth=max_depth,
                max_nodes=max_nodes,
            ):
                return False
        return True

    if isinstance(value, list):
        for item in value:
            if not _json_within_limits(
                item,
                depth=depth + 1,
                nodes=nodes,
                max_depth=max_depth,
                max_nodes=max_nodes,
            ):
                return False
        return True

    return True


class SecurityMiddleware:
    """Enforce request limits and add security/cache headers to responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        raw_headers = list(scope.get("headers") or [])
        content_length = _parse_int_header(_first_header(raw_headers, b"content-length"))

        if content_length is not None and content_length < 0:
            await self._json_response(
                scope,
                receive,
                self._send_with_headers(scope, send),
                400,
                "Invalid Content-Length header",
            )
            return

        if content_length is not None and content_length > settings.MAX_REQUEST_BODY_BYTES:
            await self._json_response(
                scope,
                receive,
                self._send_with_headers(scope, send),
                413,
                "Request body too large",
            )
            return

        body = bytearray()
        more_body = True

        while more_body:
            message = await receive()
            message_type = message.get("type")

            if message_type == "http.disconnect":
                # The client went away; there is no response worth sending.
                return

            if message_type != "http.request":
                await self.app(scope, receive, send)
                return

            body.extend(message.get("body", b""))
            if len(body) > settings.MAX_REQUEST_BODY_BYTES:
                await self._json_response(
                    scope,
                    receive,
                    self._send_with_headers(scope, send),
                    413,
                    "Request body too large",
                )
                return

            more_body = bool(message.get("more_body", False))

        if body and _content_type_is_json(_first_header(raw_headers, b"content-type")):
            try:
                parsed = json.loads(body)
            except RecursionError:
                await self._json_response(
                    scope,
                    receive,
                    self._send_with_headers(scope, send),
                    400,
                    "JSON body is too deeply nested",
                )
                return
            except Exception:
                # Let FastAPI/pydantic produce the usual 422 for malformed JSON.
                parsed = None
            else:
                if not _json_within_limits(
                    parsed,
                    depth=1,
                    nodes=[0],
                    max_depth=settings.JSON_MAX_DEPTH,
                    max_nodes=settings.JSON_MAX_NODES,
                ):
                    await self._json_response(
                        scope,
                        receive,
                        self._send_with_headers(scope, send),
                        400,
                        "JSON body is too deeply nested or too large",
                    )
                    return

        buffered_body = bytes(body)
        body_sent = False

        async def downstream_receive() -> dict[str, Any]:
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {
                    "type": "http.request",
                    "body": buffered_body,
                    "more_body": False,
                }
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, downstream_receive, self._send_with_headers(scope, send))

    async def _json_response(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        status_code: int,
        detail: str,
    ) -> None:
        response = JSONResponse(status_code=status_code, content={"detail": detail})
        await response(scope, receive, send)

    def _send_with_headers(self, scope: Scope, send: Send) -> Send:
        async def send_with_headers(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                message = {
                    **message,
                    "headers": self._headers_for_response(scope, message),
                }
            await send(message)

        return send_with_headers

    def _headers_for_response(
        self, scope: Scope, message: dict[str, Any]
    ) -> list[tuple[bytes, bytes]]:
        raw_headers = list(message.get("headers") or [])
        path = scope.get("path", "")
        authorization = _first_header(
            list(scope.get("headers") or []), b"authorization"
        )

        is_v1 = str(path).startswith("/v1")
        if is_v1 or authorization is not None:
            raw_headers = _set_header(raw_headers, b"cache-control", b"no-store")
            raw_headers = _set_header(raw_headers, b"pragma", b"no-cache")
            raw_headers = self._set_vary_authorization(raw_headers)

        raw_headers = _set_header(raw_headers, b"x-content-type-options", b"nosniff")
        raw_headers = _set_header(raw_headers, b"referrer-policy", b"no-referrer")
        raw_headers = _set_header(raw_headers, b"x-frame-options", b"DENY")
        return raw_headers

    def _set_vary_authorization(
        self, raw_headers: list[tuple[bytes, bytes]]
    ) -> list[tuple[bytes, bytes]]:
        existing = [
            value.decode("latin-1")
            for value in _header_values(raw_headers, b"vary")
        ]

        vary_values: list[str] = []
        for value in existing:
            for part in value.split(","):
                cleaned = part.strip()
                if cleaned:
                    vary_values.append(cleaned)

        if not any(value.lower() == "authorization" for value in vary_values):
            vary_values.append("Authorization")

        raw_headers = _remove_header(raw_headers, b"vary")
        if vary_values:
            raw_headers.append((b"vary", ", ".join(vary_values).encode("latin-1")))
        return raw_headers


def register_middlewares(app: FastAPI) -> None:
    # Keep body/JSON limits and response headers in a single ASGI layer so
    # early 413/400 responses get the same headers as normal responses.
    app.add_middleware(SecurityMiddleware)
