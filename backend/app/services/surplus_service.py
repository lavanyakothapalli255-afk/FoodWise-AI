"""Surplus service — Phase 3 surplus detection.

Detects surplus for a center-meal-date combination by comparing
actual production (from ProductionDecision) against consumption
(from Forecast predicted_demand or caller-supplied actual value).

Core quantities:
    surplus  = max(actual_production - actual_consumption, 0)
    shortage = max(actual_consumption - actual_production, 0)

The eligibility advisory is an informational check based on the
meal's shelf life.  It does NOT constitute a food-safety guarantee.
Final food-safety authorization must remain with a human/authorized
operator.
"""

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.models.db_models import Forecast, Meal, ProductionDecision

logger = logging.getLogger(__name__)


class SurplusService:
    """Handles surplus detection logic."""

    def detect_surplus(
        self,
        center_id: int,
        meal_id: int,
        target_date: date,
        db: Session,
        actual_consumption: int | None = None,
    ) -> dict:
        """Detect surplus for a center-meal-date combination.

        Parameters
        ----------
        center_id : int
            The production center.
        meal_id : int
            The meal type.
        target_date : date
            The date to check.
        db : Session
            SQLAlchemy database session.
        actual_consumption : int | None
            If provided, used as consumption.  Otherwise the most recent
            forecast's predicted_demand is used as a prototype proxy.

        Returns
        -------
        dict
            Surplus detection result with status, quantities, and
            eligibility advisory.
        """

        # --- 1. Get the most recent production decision with actual data ---
        decision = (
            db.query(ProductionDecision)
            .filter(
                ProductionDecision.center_id == center_id,
                ProductionDecision.meal_id == meal_id,
                ProductionDecision.date == target_date,
                ProductionDecision.actual_quantity.isnot(None),
            )
            .order_by(ProductionDecision.created_at.desc())
            .first()
        )

        if decision is None:
            logger.info(
                "No recorded production for center=%d meal=%d date=%s",
                center_id,
                meal_id,
                target_date,
            )
            return {
                "center_id": center_id,
                "meal_id": meal_id,
                "date": target_date,
                "actual_production": 0,
                "actual_consumption": 0,
                "surplus_quantity": 0,
                "shortage_quantity": 0,
                "status": "no_data",
                "eligibility_advisory": (
                    "No recorded production data found for this "
                    "center-meal-date combination."
                ),
                "usable_time_remaining_min": None,
            }

        actual_production = decision.actual_quantity

        # --- 2. Determine consumption ---
        if actual_consumption is not None:
            consumption = actual_consumption
        else:
            # Use forecast predicted_demand as prototype proxy
            forecast = (
                db.query(Forecast)
                .filter(
                    Forecast.center_id == center_id,
                    Forecast.meal_id == meal_id,
                )
                .order_by(Forecast.created_at.desc())
                .first()
            )
            if forecast is not None:
                consumption = int(round(forecast.predicted_demand))
            else:
                # Fallback: assume all produced was consumed (no surplus)
                consumption = actual_production
                logger.warning(
                    "No forecast found for center=%d meal=%d; "
                    "assuming consumption = production.",
                    center_id,
                    meal_id,
                )

        # --- 3. Compute surplus and shortage ---
        surplus = max(actual_production - consumption, 0)
        shortage = max(consumption - actual_production, 0)

        # --- 4. Eligibility advisory (shelf-life based) ---
        meal = db.query(Meal).filter(Meal.id == meal_id).first()
        usable_time_min: float | None = None
        if meal is not None:
            usable_time_min = float(meal.shelf_life_hours * 60)

        if surplus == 0:
            status = "no_surplus"
            advisory = (
                "No surplus detected. "
                "Actual production does not exceed consumption."
            )
        else:
            status = "surplus_detected"
            if usable_time_min is not None and usable_time_min > 0:
                advisory = (
                    f"Surplus of {surplus} meals detected. "
                    f"Estimated usable time: {usable_time_min:.0f} minutes "
                    f"(based on {meal.shelf_life_hours}h shelf life for "
                    f"'{meal.name}'). "
                    "Food-safety eligibility check — human authorization "
                    "required before redistribution."
                )
            else:
                advisory = (
                    f"Surplus of {surplus} meals detected. "
                    "Shelf-life data unavailable — exercise caution. "
                    "Food-safety eligibility check — human authorization "
                    "required before redistribution."
                )

        return {
            "center_id": center_id,
            "meal_id": meal_id,
            "date": target_date,
            "actual_production": actual_production,
            "actual_consumption": consumption,
            "surplus_quantity": surplus,
            "shortage_quantity": shortage,
            "status": status,
            "eligibility_advisory": advisory,
            "usable_time_remaining_min": usable_time_min,
        }


# Module-level singleton
surplus_service = SurplusService()
