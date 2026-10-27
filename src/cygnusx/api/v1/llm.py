"""Deprecated welcome endpoint; compatibility uses the DB daily delivery policy."""
from fastapi import APIRouter, Request

from cygnusx.api.deps import CurrentUserId, DbSession
from cygnusx.api.v1.welcome import claim_welcome
from cygnusx.application.schemas.welcome import ClaimRequest, ClaimResponse
from cygnusx.middleware.rbac import AdminRequired

router = APIRouter()


@router.post("/generate-welcome", deprecated=True)
async def generate_welcome(_admin: AdminRequired, request: Request,
                           user_id: CurrentUserId, db: DbSession) -> dict[str, str]:
    result = await claim_welcome(ClaimRequest(), request, user_id, db)
    return {"content": result.message if isinstance(result, ClaimResponse) else ""}
