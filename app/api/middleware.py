from __future__ import annotations

import re
from time import perf_counter
from typing import Any
from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.observability.logging import get_logger, request_logging_context


logger = get_logger("http")
_CLIENT_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


def _headers(scope: Scope, name: bytes) -> list[str]:
    return [
        value.decode("latin-1")
        for key, value in scope.get("headers", ())
        if key.lower() == name
    ]


def _error_response(status_code: int, code: str, message: str, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )


class RequestBoundaryMiddleware:
    """Create trusted request IDs and enforce a hard body-size limit.

    The complete body is bounded before FastAPI parses JSON. This also protects
    requests that omit ``Content-Length`` or use chunked transfer encoding.
    """

    def __init__(self, app: ASGIApp, *, max_request_body_bytes: int) -> None:
        self.app = app
        self.max_request_body_bytes = max_request_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid4())
        state: dict[str, Any] = scope.setdefault("state", {})
        state["request_id"] = request_id

        async def reject(status_code: int, code: str, message: str) -> None:
            logger.warning(
                "http.request.rejected",
                extra={
                    "request_id": request_id,
                    "http_method": scope.get("method"),
                    "http_path": scope.get("path"),
                    "http_status_code": status_code,
                    "rejection_code": code,
                },
            )
            response = _error_response(status_code, code, message, request_id)
            await response(scope, receive, send)

        client_request_ids = _headers(scope, b"x-client-request-id")
        if len(client_request_ids) > 1:
            await reject(
                400,
                "invalid_client_request_id",
                "X-Client-Request-ID must occur at most once.",
            )
            return
        raw_client_request_id = client_request_ids[0] if client_request_ids else None
        if raw_client_request_id is not None and not _CLIENT_REQUEST_ID.fullmatch(
            raw_client_request_id
        ):
            await reject(
                400,
                "invalid_client_request_id",
                "X-Client-Request-ID must be 1-128 URL-safe characters.",
            )
            return
        state["client_request_id"] = raw_client_request_id

        content_lengths = _headers(scope, b"content-length")
        if len(content_lengths) > 1:
            await reject(
                400,
                "invalid_content_length",
                "Content-Length must occur at most once.",
            )
            return
        content_length = content_lengths[0] if content_lengths else None
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                await reject(400, "invalid_content_length", "Content-Length is invalid.")
                return
            if declared_length < 0:
                await reject(400, "invalid_content_length", "Content-Length is invalid.")
                return
            if declared_length > self.max_request_body_bytes:
                await reject(
                    413,
                    "request_too_large",
                    "Request body exceeds the configured size limit.",
                )
                return

        body_messages: list[Message] = []
        total_bytes = 0
        while True:
            message = await receive()
            body_messages.append(message)
            if message["type"] == "http.disconnect":
                break
            if message["type"] != "http.request":
                continue
            total_bytes += len(message.get("body", b""))
            if total_bytes > self.max_request_body_bytes:
                await reject(
                    413,
                    "request_too_large",
                    "Request body exceeds the configured size limit.",
                )
                return
            if not message.get("more_body", False):
                break

        message_index = 0

        async def replay_body() -> Message:
            nonlocal message_index
            if message_index < len(body_messages):
                message = body_messages[message_index]
                message_index += 1
                return message
            return {"type": "http.disconnect"}

        status_code = 500

        async def add_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = [
                    header
                    for header in message.get("headers", ())
                    if header[0].lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        started = perf_counter()
        logger.info(
            "http.request.started",
            extra={
                "request_id": request_id,
                "client_request_id": raw_client_request_id,
                "http_method": scope.get("method"),
                "http_path": scope.get("path"),
                "request_body_bytes": total_bytes,
            },
        )
        try:
            with request_logging_context(request_id):
                await self.app(scope, replay_body, add_request_id)
        finally:
            logger.info(
                "http.request.completed",
                extra={
                    "request_id": request_id,
                    "client_request_id": raw_client_request_id,
                    "http_method": scope.get("method"),
                    "http_path": scope.get("path"),
                    "http_status_code": status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
