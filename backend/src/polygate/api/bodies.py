"""Shared helpers for parsing JSON request bodies safely."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, Request


async def read_json(request: Request) -> dict[str, Any]:
    """Read a JSON object body, rejecting malformed or non-object payloads with 400."""
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="request body is required")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail=f"invalid JSON body: {error.msg}") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")
    return payload
