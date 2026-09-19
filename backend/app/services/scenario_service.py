import logging
from sqlalchemy.orm import Session
from app.services.forecast_service import forecast_service
from app.services.production_service import production_service
from app.services.redistribution_service import redistribution_service
from app.schemas import ScenarioSimulateRequest
from app.models.db_models import Recipient

logger = logging.getLogger(__name__)

class ScenarioService:
    def simulate(self, request: ScenarioSimulateRequest, db: Session) -> dict:
        # 1. Obtain point forecast
        forecast = forecast_service.get_forecast(request.center_id, request.meal_id, db)
        if forecast is None:
            forecast = forecast_service.generate_forecast(
                request.center_id, request.meal_id, db, target_date=request.target_date
            )
        point_forecast = forecast.predicted_demand

        # 2. Baseline Decision
        baseline_metrics = production_service.compute_decision(
            center_id=request.center_id,
            meal_id=request.meal_id,
            target_date=request.target_date,
            policy="smart",
            point_forecast=point_forecast,
            demand_multiplier=1.0,
            surplus_penalty_per_meal=request.surplus_penalty_per_meal,
            shortage_penalty_per_meal=request.shortage_penalty_per_meal,
        )

        # 3. Scenario Decision
        scenario_metrics = production_service.compute_decision(
            center_id=request.center_id,
            meal_id=request.meal_id,
            target_date=request.target_date,
            policy="smart",
            point_forecast=point_forecast,
            demand_multiplier=request.demand_multiplier,
            surplus_penalty_per_meal=request.surplus_penalty_per_meal,
            shortage_penalty_per_meal=request.shortage_penalty_per_meal,
        )

        # 4. Deltas
        demand_change = scenario_metrics["simulated_demand_mean"] - baseline_metrics["simulated_demand_mean"]
        production_change = scenario_metrics["recommended_quantity"] - baseline_metrics["recommended_quantity"]
        surplus_change = scenario_metrics["expected_surplus"] - baseline_metrics["expected_surplus"]
        shortage_change = scenario_metrics["expected_shortage"] - baseline_metrics["expected_shortage"]
        cost_change = scenario_metrics["expected_decision_cost"] - baseline_metrics["expected_decision_cost"]

        # 5. Explanation
        explanations = []
        if request.demand_multiplier != 1.0:
            pct = int(round((request.demand_multiplier - 1.0) * 100))
            direction = "increased" if pct > 0 else "decreased"
            explanations.append(f"Scenario demand {direction} by {abs(pct)}%.")
        
        if request.surplus_penalty_per_meal != request.shortage_penalty_per_meal:
            if request.shortage_penalty_per_meal > request.surplus_penalty_per_meal:
                explanations.append("Shortage avoidance received greater weight.")
            else:
                explanations.append("Surplus avoidance received greater weight.")

        for override in request.recipient_availability_overrides:
            if not override.is_available:
                explanations.append(f"Recipient ID {override.recipient_id} was unavailable in the scenario.")

        explanation = " ".join(explanations) if explanations else "No scenario assumptions were changed."

        # 6. Redistribution (if surplus > 0 in scenario)
        redistribution_result = None
        surplus_qty = max(0, scenario_metrics["recommended_quantity"] - int(round(scenario_metrics["simulated_demand_mean"])))
        
        if surplus_qty > 0:
            recipients = db.query(Recipient).filter(Recipient.is_active == True).all()
            override_map = {ov.recipient_id: ov.is_available for ov in request.recipient_availability_overrides}
            
            op_data = []
            for r in recipients:
                is_avail = override_map.get(r.id, True)
                if is_avail:
                    op_data.append({
                        "recipient_id": r.id,
                        "distance_km": 10.0,
                        "transit_time_min": 30.0,
                        "usable_time_remaining_min": 120.0,
                        "priority": 1,
                    })

            if op_data:
                redistribution_result = redistribution_service.optimize(
                    center_id=request.center_id,
                    meal_id=request.meal_id,
                    target_date=request.target_date,
                    surplus_qty=surplus_qty,
                    recipient_overrides=op_data,
                    db=db,
                    persist=False,
                )

        return {
            "baseline": {
                "point_forecast": baseline_metrics["point_forecast"],
                "simulated_demand_mean": baseline_metrics["simulated_demand_mean"],
                "recommended_quantity": baseline_metrics["recommended_quantity"],
                "expected_surplus": baseline_metrics["expected_surplus"],
                "expected_shortage": baseline_metrics["expected_shortage"],
                "decision_cost": baseline_metrics["expected_decision_cost"],
            },
            "scenario": {
                "point_forecast": scenario_metrics["point_forecast"],
                "simulated_demand_mean": scenario_metrics["simulated_demand_mean"],
                "recommended_quantity": scenario_metrics["recommended_quantity"],
                "expected_surplus": scenario_metrics["expected_surplus"],
                "expected_shortage": scenario_metrics["expected_shortage"],
                "decision_cost": scenario_metrics["expected_decision_cost"],
            },
            "changes": {
                "demand_change": round(demand_change, 2),
                "production_change": production_change,
                "surplus_change": round(surplus_change, 2),
                "shortage_change": round(shortage_change, 2),
                "cost_change": round(cost_change, 2),
            },
            "redistribution": redistribution_result,
            "explanation": explanation
        }

scenario_service = ScenarioService()
