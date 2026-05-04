"""Tencent Cloud SCF entrypoint for the FastAPI backend.

Upload the repository with `backend/` at the zip root and set the SCF handler
to `scf_index.main_handler` through the root wrapper, or to
`backend.scf_index.main_handler` if the console accepts package handlers.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
from typing import Any
from urllib.parse import urlencode, unquote

from backend.main import app


def main_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    """Tencent Cloud SCF API Gateway handler."""
    try:
        return asyncio.run(_handle(event))
    except Exception as exc:  # pragma: no cover - defensive cloud fallback
        return _response(
            status_code=500,
            headers={"content-type": "application/json; charset=utf-8"},
            body=json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False).encode("utf-8"),
        )


async def _handle(event: dict[str, Any]) -> dict[str, Any]:
    status_code = 500
    response_headers: list[tuple[bytes, bytes]] = []
    body_chunks: list[bytes] = []

    request_body = _decode_body(event)
    request_headers = _normalize_headers(event.get("headers") or {})
    consumed = False

    async def receive() -> dict[str, Any]:
        nonlocal consumed
        if consumed:
            return {"type": "http.disconnect"}
        consumed = True
        return {"type": "http.request", "body": request_body, "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        nonlocal status_code, response_headers
        if message["type"] == "http.response.start":
            status_code = int(message["status"])
            response_headers = list(message.get("headers") or [])
        elif message["type"] == "http.response.body":
            body_chunks.append(message.get("body", b""))

    await app(_build_scope(event, request_headers), receive, send)

    headers = {
        key.decode("latin-1"): value.decode("latin-1")
        for key, value in response_headers
    }
    return _response(status_code=status_code, headers=headers, body=b"".join(body_chunks))


def _build_scope(
    event: dict[str, Any],
    headers: list[tuple[bytes, bytes]],
) -> dict[str, Any]:
    path = _normalize_path(str(event.get("path") or event.get("rawPath") or "/"))
    query_string = _build_query_string(event)
    if "?" in path:
        path, inline_query = path.split("?", 1)
        query_string = inline_query.encode("utf-8") if not query_string else query_string

    method = str(event.get("httpMethod") or event.get("requestContext", {}).get("httpMethod") or "GET")

    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "https",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": query_string,
        "headers": headers,
        "client": ("0.0.0.0", 0),
        "server": ("serverless", 443),
        "root_path": "",
    }


def _normalize_path(raw_path: str) -> str:
    path = unquote(raw_path or "/")
    if not path.startswith("/"):
        path = f"/{path}"

    configured_prefix = os.getenv("SCF_PATH_PREFIX", "").strip().rstrip("/")
    if configured_prefix and path.startswith(configured_prefix):
        path = path[len(configured_prefix) :] or "/"

    if not path.startswith("/api") and "/api/" in path:
        path = path[path.index("/api/") :]
    return path


def _normalize_headers(headers: dict[str, Any]) -> list[tuple[bytes, bytes]]:
    normalized: list[tuple[bytes, bytes]] = []
    for key, value in headers.items():
        if value is None:
            continue
        if isinstance(value, list):
            values = value
        else:
            values = [value]
        for item in values:
            normalized.append((str(key).lower().encode("latin-1"), str(item).encode("latin-1")))
    return normalized


def _build_query_string(event: dict[str, Any]) -> bytes:
    raw_query = event.get("rawQueryString") or event.get("queryString")
    if isinstance(raw_query, str):
        return raw_query.encode("utf-8")

    params = event.get("queryStringParameters") or {}
    if isinstance(params, dict) and params:
        return urlencode(params, doseq=True).encode("utf-8")
    return b""


def _decode_body(event: dict[str, Any]) -> bytes:
    body = event.get("body") or b""
    if isinstance(body, dict):
        body = json.dumps(body, ensure_ascii=False)
    if isinstance(body, str):
        raw = body.encode("utf-8")
    else:
        raw = bytes(body)

    if event.get("isBase64Encoded"):
        return base64.b64decode(raw)
    return raw


def _response(status_code: int, headers: dict[str, str], body: bytes) -> dict[str, Any]:
    content_type = headers.get("content-type") or headers.get("Content-Type") or ""
    is_text = (
        content_type.startswith("application/json")
        or content_type.startswith("text/")
        or "charset=" in content_type
    )

    if is_text:
        response_body = body.decode("utf-8", errors="replace")
        is_base64 = False
    else:
        response_body = base64.b64encode(body).decode("ascii")
        is_base64 = True

    return {
        "isBase64Encoded": is_base64,
        "statusCode": status_code,
        "headers": headers,
        "body": response_body,
    }
