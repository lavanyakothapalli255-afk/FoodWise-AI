"""Forecast router — demand forecast endpoints."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ForecastRead, ForecastRequest, HistoricalObservation
from app.services.forecast_service import forecast_service

router = APIRouter()


@router.post("/generate", response_model=ForecastRead)
def generate_forecast(
    payload: ForecastRequest, db: Session = Depends(get_db)
):
    """Generate a demand forecast for a centre–meal pair.

    Uses a HistGradientBoosting model trained on historical order data
    (Experiment 1 methodology).  Confidence bounds are derived from
    the Experiment 2 OOS residual pool.
    """
    forecast = forecast_service.generate_forecast(
        payload.center_id, payload.meal_id, db, target_date=payload.target_date
    )
    return forecast


@router.get("/{center_id}/{meal_id}", response_model=ForecastRead)
def get_forecast(
    center_id: int, meal_id: int, db: Session = Depends(get_db)
):
    """Retrieve the most recent forecast for a centre–meal pair."""
    forecast = forecast_service.get_forecast(center_id, meal_id, db)
    if forecast is None:
        raise HTTPException(
            status_code=404,
            detail="No forecast found for this centre–meal pair",
        )
    return forecast


@router.get("/history/{center_id}/{meal_id}", response_model=List[HistoricalObservation])
def get_forecast_history(
    center_id: int, meal_id: int, db: Session = Depends(get_db)
):
    """Retrieve the recent historical demand context for a centre-meal pair."""
    history = forecast_service.get_recent_history(center_id, meal_id)
    if history is None:
        raise HTTPException(
            status_code=404,
            detail="No historical context found for this centre-meal pair",
        )
    return history
