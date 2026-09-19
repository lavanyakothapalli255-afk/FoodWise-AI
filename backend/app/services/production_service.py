"""Production service — Experiment 2 methodology (residual-based policies).

Implements the adaptive production decision framework from Experiment 2:
  1. Fetch or generate a point forecast (from forecast_service).
  2. Monte Carlo simulation: draw 1000 residuals from the Experiment 2
     OOS residual pool, compute d_sim = max(0, forecast + residual).
  3. Apply the requested policy (a percentile of the simulated demand
     distribution, or the training-period historical mean).
  4. Compute expected surplus and expected shortage from the simulation
     to make the service-level/waste trade-off explicit.

Available policies and their roles:
  - p50:  point forecast — lowest surplus, highest shortage risk
  - p70:  moderate safety buffer
  - p80:  prototype default (balanced, NOT universally optimal)
  - p90:  conservative buffer
  - p95:  aggressive buffer — lowest shortage risk, highest surplus
  - historical_mean: baseline using per-pair training-period average

Each policy represents a different trade-off.  The caller chooses the
policy that matches their operational priority (service level vs. waste).
"""

import hashlib
import logging
import os

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models.db_models import ProductionDecision
from app.services.forecast_service import forecast_service

logger = logging.getLogger(__name__)

_SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SERVICE_DIR, "..", "..", ".."))
_RESIDUAL_CSV = os.path.join(
    _PROJECT_ROOT, "experiments", "experiment_2_validation_residuals.csv"
)

# Monte Carlo sample count (matches Experiment 2)
N_SAMPLES = 1000

# Percentile lookup for each policy
POLICY_PERCENTILES = {
    "p50": 50,
    "p70": 70,
    "p80": 80,
    "p90": 90,
    "p95": 95,
}

VALID_POLICIES = set(POLICY_PERCENTILES.keys()) | {"historical_mean", "smart"}


class ProductionService:
    """Adaptive production decisions following Experiment 2."""

    def __init__(self) -> None:
        self._residual_pool: np.ndarray | None = None
        self._loaded: bool = False

    def _ensure_loaded(self) -> None:
        """Load the OOS residual pool on first use."""
        if self._loaded:
            return
        if os.path.exists(_RESIDUAL_CSV):
            residuals_df = pd.read_csv(_RESIDUAL_CSV)
            self._residual_pool = residuals_df["residual"].to_numpy()
            logger.info(
                "Loaded %d OOS residuals from Experiment 2.",
                len(self._residual_pool),
            )
        else:
            logger.warning("Residual CSV not found at %s", _RESIDUAL_CSV)
            self._residual_pool = np.array([0.0])
        self._loaded = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_decision(
        self,
        center_id: int,
        meal_id: int,
        target_date,
        policy: str,
        point_forecast: float,
        demand_multiplier: float = 1.0,
        surplus_penalty_per_meal: float = None,
        shortage_penalty_per_meal: float = None,
    ) -> dict:
        """Compute the production decision metrics without DB persistence.
        
        Applies a demand_multiplier to the simulated demand distribution.
        """
        self._ensure_loaded()
        
        # --- 2. Monte Carlo simulation ---
        seed_str = f"{center_id}_{meal_id}_{target_date}"
        seed_int = int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest(), 16) % (2**31)
        rng = np.random.default_rng(seed_int)
        sampled_residuals = rng.choice(
            self._residual_pool, size=N_SAMPLES, replace=True
        )
        d_sim = np.maximum(0.0, point_forecast + sampled_residuals)
        
        # Apply scenario multiplier to the simulated demand
        d_sim = d_sim * demand_multiplier

        decision_mode = None
        expected_decision_cost = None
        explanation = None

        # --- 3. Apply policy ---
        if policy == "historical_mean":
            forecast_service._ensure_trained()
            csv_cid, csv_mid = forecast_service.map_ids(center_id, meal_id)
            hist_mean = forecast_service._historical_means.get(
                (csv_cid, csv_mid), forecast_service._overall_train_mean
            )
            recommended_qty = int(round(hist_mean * demand_multiplier))
        elif policy == "smart":
            lower_bound = max(0, int(np.floor(np.min(d_sim))))
            upper_bound = int(np.ceil(np.max(d_sim)))
            candidates = np.arange(lower_bound, upper_bound + 1)
            
            C = candidates[:, np.newaxis]
            D = d_sim[np.newaxis, :]
            
            surplus_matrix = np.maximum(C - D, 0.0)
            shortage_matrix = np.maximum(D - C, 0.0)
            
            E_surplus = np.mean(surplus_matrix, axis=1)
            E_shortage = np.mean(shortage_matrix, axis=1)
            
            E_cost = surplus_penalty_per_meal * E_surplus + shortage_penalty_per_meal * E_shortage
            
            best_idx = int(np.argmin(E_cost))
            recommended_qty = int(candidates[best_idx])
            expected_decision_cost = float(E_cost[best_idx])
            decision_mode = "smart_cost_minimization"
            explanation = f"Selected {recommended_qty} meals because this quantity minimizes the expected decision penalty under the supplied surplus and shortage penalties."
        else:
            percentile = POLICY_PERCENTILES[policy]
            recommended_qty = int(round(float(np.percentile(d_sim, percentile))))

        recommended_qty = max(0, recommended_qty)

        # --- 4. Expected surplus / shortage ---
        q = float(recommended_qty)
        expected_surplus = float(np.mean(np.maximum(q - d_sim, 0.0)))
        expected_shortage = float(np.mean(np.maximum(d_sim - q, 0.0)))

        return {
            "policy_used": policy,
            "point_forecast": round(point_forecast, 2),
            "simulated_demand_mean": float(np.mean(d_sim)),
            "recommended_quantity": recommended_qty,
            "expected_surplus": round(expected_surplus, 2),
            "expected_shortage": round(expected_shortage, 2),
            "decision_mode": decision_mode,
            "expected_decision_cost": round(expected_decision_cost, 2) if expected_decision_cost is not None else None,
            "surplus_penalty_per_meal": surplus_penalty_per_meal,
            "shortage_penalty_per_meal": shortage_penalty_per_meal,
            "explanation": explanation,
        }

    def recommend(
        self,
        center_id: int,
        meal_id: int,
        target_date,
        policy: str,
        db: Session,
        surplus_penalty_per_meal: float = None,
        shortage_penalty_per_meal: float = None,
    ) -> dict:
        """Compute a production recommendation for a centre–meal–date.

        Returns a dict with the DB-persisted ProductionDecision fields
        plus computed trade-off transparency fields.
        """
        if policy not in VALID_POLICIES:
            raise ValueError(
                f"Invalid policy '{policy}'. "
                f"Choose from: {sorted(VALID_POLICIES)}"
            )

        # --- 1. Obtain point forecast ---
        forecast = forecast_service.get_forecast(center_id, meal_id, db)
        if forecast is None:
            forecast = forecast_service.generate_forecast(
                center_id, meal_id, db, target_date=target_date
            )
        point_forecast = forecast.predicted_demand

        # --- Compute Decision Metrics ---
        metrics = self.compute_decision(
            center_id=center_id,
            meal_id=meal_id,
            target_date=target_date,
            policy=policy,
            point_forecast=point_forecast,
            demand_multiplier=1.0,
            surplus_penalty_per_meal=surplus_penalty_per_meal,
            shortage_penalty_per_meal=shortage_penalty_per_meal,
        )

        # --- 5. Persist to production_decisions ---
        decision = ProductionDecision(
            center_id=center_id,
            meal_id=meal_id,
            date=target_date,
            recommended_quantity=metrics["recommended_quantity"],
            decision_status="pending",
        )
        db.add(decision)
        db.commit()
        db.refresh(decision)

        return {
            "id": decision.id,
            "center_id": decision.center_id,
            "meal_id": decision.meal_id,
            "date": decision.date,
            "recommended_quantity": decision.recommended_quantity,
            "actual_quantity": decision.actual_quantity,
            "decision_status": decision.decision_status,
            "created_at": decision.created_at,
            "policy_used": metrics["policy_used"],
            "point_forecast": metrics["point_forecast"],
            "expected_surplus": metrics["expected_surplus"],
            "expected_shortage": metrics["expected_shortage"],
            "decision_mode": metrics["decision_mode"],
            "expected_decision_cost": metrics["expected_decision_cost"],
            "surplus_penalty_per_meal": metrics["surplus_penalty_per_meal"],
            "shortage_penalty_per_meal": metrics["shortage_penalty_per_meal"],
            "explanation": metrics["explanation"],
        }

    def record_actual(
        self,
        center_id: int,
        meal_id: int,
        target_date,
        actual_quantity: int,
        db: Session,
    ) -> ProductionDecision | None:
        """Record actual production against the most recent decision.

        Updates the matching ProductionDecision row with the actual
        quantity and sets decision_status to 'recorded'.
        """
        decision = (
            db.query(ProductionDecision)
            .filter(
                ProductionDecision.center_id == center_id,
                ProductionDecision.meal_id == meal_id,
                ProductionDecision.date == target_date,
            )
            .order_by(ProductionDecision.created_at.desc())
            .first()
        )
        if decision is None:
            return None

        decision.actual_quantity = actual_quantity
        decision.decision_status = "recorded"
        db.commit()
        db.refresh(decision)
        return decision


# Module-level singleton
production_service = ProductionService()
