"""First-run password setup, login and session logout for the admin console."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from polygate.api.auth import _bearer, require_admin
from polygate.password import (
    MIN_PASSWORD_LENGTH,
    SESSION_TTL_SECONDS,
    hash_password,
    new_session_token,
    session_digest,
    verify_password,
)

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


class PasswordBody(BaseModel):
    """Password input for setup and login."""

    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=200)


@router.get("/status")
async def auth_status(request: Request) -> dict[str, bool]:
    """Report whether the first-run password has been configured."""
    configured = await request.app.state.store.admin_password_configured()
    return {"configured": configured}


@router.post("/setup")
async def setup_password(body: PasswordBody, request: Request) -> dict[str, str]:
    """Set the first-run password and return a browser session token."""
    try:
        encoded = hash_password(body.password)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if not await request.app.state.store.set_admin_password(encoded):
        raise HTTPException(status_code=409, detail="admin password is already configured")
    return await _new_session(request)


@router.post("/login")
async def login_password(body: PasswordBody, request: Request) -> dict[str, str]:
    """Verify a password and return a browser session token."""
    encoded = await request.app.state.store.get_admin_password_hash()
    if encoded is None:
        raise HTTPException(status_code=409, detail="admin password is not configured")
    if not verify_password(body.password, encoded):
        raise HTTPException(status_code=401, detail="invalid admin password")
    return await _new_session(request)


@router.post("/logout", dependencies=[Depends(require_admin)])
async def logout(request: Request) -> dict[str, bool]:
    """Revoke the current browser session token."""
    token = _bearer(request)
    if token:
        await request.app.state.store.delete_admin_session(session_digest(token))
    return {"ok": True}


async def _new_session(request: Request) -> dict[str, str]:
    """Create and persist a browser session token."""
    token = new_session_token()
    await request.app.state.store.create_admin_session(
        session_digest(token), time.time() + SESSION_TTL_SECONDS
    )
    return {"token": token}
