"""Production router — production recommendation and recording endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    ProductionDecisionRead,
    ProductionRecommendRequest,
    ProductionRecommendResponse,
    ProductionRecordRequest,
)
from app.services.production_service import production_service

router = APIRouter()


@router.post("/recommend", response_model=ProductionRecommendResponse)
def recommend_production(
    payload: ProductionRecommendRequest, db: Session = Depends(get_db)
):
    """Recommend a production quantity for a centre–meal–date.

    Uses the Experiment 2 methodology: Monte Carlo simulation with
    1000 residual draws from the OOS pool, then applies the requested
    percentile policy.  The response includes expected surplus and
    expected shortage so the caller can see the trade-off explicitly.

    Available policies (each is a different trade-off, none is
    universally optimal):
      p50  — point forecast (lowest waste, highest shortage risk)
      p70  — moderate buffer
      p80  — prototype default (balanced)
      p90  — conservative buffer
      p95  — aggressive buffer (lowest shortage risk, highest waste)
      historical_mean — training-period baseline
    """
    result = production_service.recommend(
        center_id=payload.center_id,
        meal_id=payload.meal_id,
        target_date=payload.date,
        policy=payload.policy,
        db=db,
    )
    return result


@router.post("/record", response_model=ProductionDecisionRead)
def record_production(
    payload: ProductionRecordRequest, db: Session = Depends(get_db)
):
    """Record actual production against the most recent decision."""
    decision = production_service.record_actual(
        center_id=payload.center_id,
        meal_id=payload.meal_id,
        target_date=payload.date,
        actual_quantity=payload.actual_quantity,
        db=db,
    )
    if decision is None:
        raise HTTPException(
            status_code=404,
            detail="No production decision found for this centre–meal–date",
        )
    return decision
