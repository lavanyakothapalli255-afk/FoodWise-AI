"""Redistribution router — Phase 3 optimization and authorization endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    RedistributionAuthorizeRequest,
    RedistributionOptimizeRequest,
    RedistributionOptimizeResponse,
    RedistributionPlanRead,
)
from app.services.redistribution_service import redistribution_service

router = APIRouter()


@router.post("/optimize", response_model=RedistributionOptimizeResponse)
def optimize_redistribution(
    payload: RedistributionOptimizeRequest, db: Session = Depends(get_db)
):
    """Optimize surplus redistribution using the 3-stage lexicographic LP.

    This is an operational-feasibility optimization.  It enforces:
      - allocation <= surplus
      - allocation <= recipient capacity
      - unavailable recipient receives zero
      - transit_time > usable_time → allocation = 0
      - non-negative allocations

    The resulting plan has status='recommended' and requires human
    authorization via POST /api/redistribution/authorize before
    becoming final.

    Recipient operational data (distance, transit time, usable time,
    priority) is provided per-request via recipient_overrides because
    these values are event-specific, not static recipient attributes.
    """
    # Convert Pydantic models to dicts for the service
    overrides = [entry.model_dump() for entry in payload.recipient_overrides]

    result = redistribution_service.optimize(
        center_id=payload.center_id,
        meal_id=payload.meal_id,
        target_date=payload.date,
        surplus_qty=payload.surplus_quantity,
        recipient_overrides=overrides,
        db=db,
    )
    return result


@router.post("/authorize", response_model=RedistributionPlanRead)
def authorize_redistribution(
    payload: RedistributionAuthorizeRequest, db: Session = Depends(get_db)
):
    """Authorize a redistribution plan.

    Changes the plan status from 'recommended' to 'authorized' and
    records who authorized it.  This is the final step in the
    DETECT → DECIDE → RESCUE workflow.

    Final food-safety responsibility remains with the authorizing
    human operator.
    """
    plan = redistribution_service.authorize(
        plan_id=payload.plan_id,
        authorized_by=payload.authorized_by,
        db=db,
    )
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail=f"Redistribution plan {payload.plan_id} not found",
        )
    return plan
