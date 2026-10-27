"""Optional welcome UI endpoints: DB reads/reservations only, never LLM calls."""

import time
from uuid import UUID

from fastapi import APIRouter, Request, Response
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from cygnusx.api.deps import CurrentUserId, DbSession
from cygnusx.application.schemas.welcome import ClaimRequest, ClaimResponse, ImpressionRequest
from cygnusx.application.services.welcome import metrics
from cygnusx.application.services.welcome.distribution import claim, impression
from cygnusx.core.security import decode_token

router = APIRouter()


def is_first_session(request: Request) -> bool:
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    return bool((decode_token(token) or {}).get("onboarding_session"))


@router.post(
    "/claim", response_model=ClaimResponse, responses={204: {"description": "No welcome due"}}
)
async def claim_welcome(
    req: ClaimRequest, request: Request, user_id: CurrentUserId, db: DbSession
) -> ClaimResponse | Response:
    started = time.perf_counter()
    try:
        delivery = await claim(db, UUID(user_id), first_session=is_first_session(request))
        if delivery is None:
            return Response(status_code=204)
        result = ClaimResponse(
            delivery_id=delivery.id,
            reservation_expires_at=delivery.reservation_expires_at,
            message=delivery.text,
            source=delivery.source,
        )
        await db.commit()  # The reservation must be durable before the UI can display it.
        return result
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.warning("Welcome claim unavailable ({})", type(exc).__name__)
        return Response(status_code=204)
    finally:
        metrics.claim_latency.record((time.perf_counter() - started) * 1000)


@router.post("/impression")
async def confirm_impression(
    req: ImpressionRequest, user_id: CurrentUserId, db: DbSession
) -> dict[str, bool]:
    try:
        accepted = await impression(db, UUID(user_id), req.delivery_id)
        await db.commit()
        return {"accepted": accepted}
    except SQLAlchemyError:
        await db.rollback()
        return {"accepted": False}
