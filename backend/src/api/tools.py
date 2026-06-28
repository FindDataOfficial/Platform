"""Tools HTTP API (T033, US3, contracts/http-api.md).

GET /api/tools — list registered tool descriptors (FR-013).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.auth import require_user
from src.models.entities import User
from src.tools.registry import all_descriptors, to_public

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
def list_tools(_user: User = Depends(require_user)):
    return [to_public(d) for d in all_descriptors()]
