"""Admin API for generating, listing and revoking caller API keys."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from polygate.api.auth import require_admin
from polygate.api.deps import gateway_of
from polygate.api_keys import generate_api_key

router = APIRouter(prefix="/admin/api-keys", tags=["admin-api-keys"], dependencies=[Depends(require_admin)])


class ApiKeyCreate(BaseModel):
    """Fields accepted when generating a caller API key."""

    name: str = Field(min_length=1, max_length=80)
    tier: Literal["premium", "standard", "economy"] = "standard"
    allowed_providers: list[str] = Field(min_length=1)


@router.get("")
async def list_api_keys(request: Request) -> dict[str, object]:
    """List key metadata; plaintext secrets are never returned."""
    return {"keys": await request.app.state.store.list_api_keys()}


@router.post("")
async def create_api_key(body: ApiKeyCreate, request: Request) -> dict[str, object]:
    """Generate a key and return its plaintext exactly once."""
    gateway = gateway_of(request)
    known = {provider.id for provider in gateway.providers}
    unknown = sorted(set(body.allowed_providers) - known)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown providers: {', '.join(unknown)}")
    generated = generate_api_key()
    await request.app.state.store.create_api_key(
        generated.id,
        body.name,
        generated.prefix,
        generated.key_hash,
        body.tier,
        body.allowed_providers,
    )
    return {
        "id": generated.id,
        "name": body.name,
        "prefix": generated.prefix,
        "tier": body.tier,
        "allowed_providers": body.allowed_providers,
        "token": generated.token,
    }


@router.delete("/{key_id}")
async def revoke_api_key(key_id: str, request: Request) -> dict[str, bool]:
    """Revoke a generated key; it will no longer authenticate."""
    if not await request.app.state.store.revoke_api_key(key_id):
        raise HTTPException(status_code=404, detail="api key not found")
    return {"ok": True}
