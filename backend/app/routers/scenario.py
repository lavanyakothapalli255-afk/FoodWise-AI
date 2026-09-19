from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ScenarioSimulateRequest, ScenarioSimulateResponse
from app.services.scenario_service import scenario_service

router = APIRouter()

@router.post("/simulate", response_model=ScenarioSimulateResponse)
def simulate_scenario(
    payload: ScenarioSimulateRequest, db: Session = Depends(get_db)
):
    """Simulate a what-if scenario for a given center, meal, and date."""
    result = scenario_service.simulate(payload, db)
    return result
