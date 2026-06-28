"""LLM management HTTP API (T024/T025, US2, contracts/http-api.md).

Provider/model CRUD. API keys encrypted at rest (R4) and NEVER returned (FR-018/020).
Model enable/disable (FR-022).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import require_user
from src.llm.secrets import encrypt
from src.models.db import get_db
from src.models.entities import LlmModel, LlmProvider, ProviderType, User

router = APIRouter(prefix="/api/llm", tags=["llm"])


class ProviderIn(BaseModel):
    name: str
    type: ProviderType
    base_url: str
    api_key: str


class ProviderPatch(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None  # rotate


class ModelIn(BaseModel):
    provider_id: uuid.UUID
    model_name: str
    display_name: str
    input_price_per_1m: float | None = None
    output_price_per_1m: float | None = None


class ModelPatch(BaseModel):
    enabled: bool | None = None
    display_name: str | None = None


def _provider_out(p: LlmProvider) -> dict:
    # FR-018/FR-020: NEVER include api_key or ciphertext.
    return {
        "id": str(p.id),
        "name": p.name,
        "type": p.type.value,
        "base_url": p.base_url,
    }


def _model_out(m: LlmModel) -> dict:
    return {
        "id": str(m.id),
        "provider_id": str(m.provider_id),
        "model_name": m.model_name,
        "display_name": m.display_name,
        "enabled": m.enabled,
    }


@router.get("/providers")
def list_providers(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.execute(select(LlmProvider).where(LlmProvider.owner_id == user.id)).scalars()
    return [_provider_out(p) for p in rows]


@router.post("/providers")
def create_provider(body: ProviderIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    p = LlmProvider(
        owner_id=user.id,
        name=body.name,
        type=body.type,
        base_url=body.base_url,
        api_key_ciphertext=encrypt(body.api_key),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _provider_out(p)


@router.patch("/providers/{provider_id}")
def update_provider(
    provider_id: uuid.UUID,
    body: ProviderPatch,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    p = db.get(LlmProvider, provider_id)
    if p is None or p.owner_id != user.id:
        raise HTTPException(404, "provider not found")
    if body.name is not None:
        p.name = body.name
    if body.base_url is not None:
        p.base_url = body.base_url
    if body.api_key is not None:
        p.api_key_ciphertext = encrypt(body.api_key)
    db.commit()
    return _provider_out(p)


@router.delete("/providers/{provider_id}")
def delete_provider(provider_id: uuid.UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    p = db.get(LlmProvider, provider_id)
    if p is None or p.owner_id != user.id:
        raise HTTPException(404, "provider not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.get("/models")
def list_models(enabled: bool | None = None, user: User = Depends(require_user), db: Session = Depends(get_db)):
    prov_ids = {p.id for p in db.execute(select(LlmProvider).where(LlmProvider.owner_id == user.id)).scalars()}
    rows = db.execute(select(LlmModel)).scalars()
    out = []
    for m in rows:
        if m.provider_id not in prov_ids:
            continue
        if enabled is not None and m.enabled != enabled:
            continue
        out.append(_model_out(m))
    return out


@router.post("/models")
def create_model(body: ModelIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    p = db.get(LlmProvider, body.provider_id)
    if p is None or p.owner_id != user.id:
        raise HTTPException(404, "provider not found")
    m = LlmModel(
        provider_id=p.id,
        model_name=body.model_name,
        display_name=body.display_name,
        input_price_per_1m=body.input_price_per_1m,
        output_price_per_1m=body.output_price_per_1m,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return _model_out(m)


@router.patch("/models/{model_id}")
def update_model(model_id: uuid.UUID, body: ModelPatch, user: User = Depends(require_user), db: Session = Depends(get_db)):
    m = db.get(LlmModel, model_id)
    if m is None:
        raise HTTPException(404, "model not found")
    p = db.get(LlmProvider, m.provider_id)
    if p is None or p.owner_id != user.id:
        raise HTTPException(404, "model not found")
    if body.enabled is not None:
        m.enabled = body.enabled  # FR-022
    if body.display_name is not None:
        m.display_name = body.display_name
    db.commit()
    db.refresh(m)
    return _model_out(m)
