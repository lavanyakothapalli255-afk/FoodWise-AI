"""Surplus router — Phase 3 surplus detection endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SurplusDetectRequest, SurplusDetectResponse
from app.services.surplus_service import surplus_service

router = APIRouter()


@router.post("/detect", response_model=SurplusDetectResponse)
def detect_surplus(
    payload: SurplusDetectRequest, db: Session = Depends(get_db)
):
    """Detect surplus food for a center-meal-date.

    Compares actual production (from recorded production decisions)
    against consumption (caller-supplied or forecast-based proxy).

    Returns surplus/shortage quantities, status, and an eligibility
    advisory.  The advisory is informational only — final food-safety
    authorization must be performed by a human/authorized operator.
    """
    result = surplus_service.detect_surplus(
        center_id=payload.center_id,
        meal_id=payload.meal_id,
        target_date=payload.date,
        db=db,
        actual_consumption=payload.actual_consumption,
    )
    return result
