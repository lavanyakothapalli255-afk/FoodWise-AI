"""Dashboard router for Phase 1 MVP."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.db_models import (
    Center,
    Meal,
    Recipient,
    Forecast,
    ProductionDecision,
    RedistributionPlan,
)
from app.schemas import DashboardSummary

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)):
    """Return dashboard summary using actual DB metrics."""
    total_centers = db.query(func.count(Center.id)).scalar() or 0
    total_meals = db.query(func.count(Meal.id)).scalar() or 0
    total_recipients = db.query(func.count(Recipient.id)).scalar() or 0
    total_forecasts = db.query(func.count(Forecast.id)).scalar() or 0
    total_production_decisions = db.query(func.count(ProductionDecision.id)).scalar() or 0
    total_redistribution_plans = db.query(func.count(RedistributionPlan.id)).scalar() or 0
    
    authorized_plans = (
        db.query(func.count(RedistributionPlan.id))
        .filter(RedistributionPlan.authorized_by.isnot(None))
        .scalar() or 0
    )

    return DashboardSummary(
        total_centers=total_centers,
        total_meals=total_meals,
        total_recipients=total_recipients,
        total_forecasts=total_forecasts,
        total_production_decisions=total_production_decisions,
        total_redistribution_plans=total_redistribution_plans,
        authorized_plans=authorized_plans,
    )
