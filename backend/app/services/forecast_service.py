"""Forecast service — Experiment 1 methodology (HistGradientBoosting).

Trains a HistGradientBoostingRegressor on the food demand training data
following the exact methodology from Experiment 1:
  - 7 categorical features (center_id, meal_id, center_type, city_code,
    region_code, category, cuisine)
  - 15 numeric features (prices, discount_ratio, promotions, week cyclicals,
    lag-1/2/4, rolling-mean-4/8)
  - Training split: weeks 1–135 (frozen origin)
  - Lag/rolling features: built only from training-period actuals (no leakage)

Confidence bounds use the Experiment 2 OOS residual pool (10th/90th
percentile of point_forecast + sampled residuals).

For the prototype, the model trains once on first use.  The training CSV
uses its own center_id / meal_id integer codes (77 centres, 51 meals).
Our seed database has 3 centres (1-3) and 4 meals (1-4), so the service
maintains a deterministic mapping from DB IDs to representative CSV IDs.
"""

import logging
import os
from datetime import date as date_type

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import OrdinalEncoder
from sqlalchemy.orm import Session

from app.models.db_models import Forecast

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths — resolved relative to this file, never modified
# ---------------------------------------------------------------------------
_SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
_ARTIFACT_PATH = os.path.abspath(os.path.join(
    _SERVICE_DIR, "..", "..", "artifacts", "forecast_model_v1.joblib"
))

# ---------------------------------------------------------------------------
# Feature lists (identical to Experiment 1)
# ---------------------------------------------------------------------------
CATEGORICAL_FEATURES = [
    "center_id",
    "meal_id",
    "center_type",
    "city_code",
    "region_code",
    "category",
    "cuisine",
]
NUMERIC_FEATURES = [
    "checkout_price",
    "base_price",
    "discount_ratio",
    "emailer_for_promotion",
    "homepage_featured",
    "op_area",
    "week",
    "week_mod_52",
    "week_sin",
    "week_cos",
    "lag_1",
    "lag_2",
    "lag_4",
    "rolling_mean_4",
    "rolling_mean_8",
]


class ForecastService:
    """Demand forecasting following Experiment 1 (HistGradientBoosting)."""

    def __init__(self) -> None:
        self._model: HistGradientBoostingRegressor | None = None
        self._encoder: OrdinalEncoder | None = None
        self._trained: bool = False

        # (csv_center_id, csv_meal_id) → feature-value dict for last known week
        self._last_known_features: dict[tuple[int, int], dict] = {}

        # (csv_center_id, csv_meal_id) → mean num_orders over training weeks
        self._historical_means: dict[tuple[int, int], float] = {}
        self._overall_train_mean: float = 0.0

        # (csv_center_id, csv_meal_id) → list of last 8 actual observations
        self._recent_history: dict[tuple[int, int], list[dict]] = {}

        # Prototype mapping: DB ID → representative CSV ID
        self._db_center_to_csv: dict[int, int] = {}
        self._db_meal_to_csv: dict[int, int] = {}

        # Residual pool for confidence bounds (Experiment 2)
        self._residual_pool: np.ndarray | None = None

    # ------------------------------------------------------------------
    # Lazy initialisation
    # ------------------------------------------------------------------

    def _ensure_trained(self) -> None:
        """Load artifact on first use so app startup remains fast."""
        if self._trained:
            return
        self._load_artifact()
        self._trained = True

    # ------------------------------------------------------------------
    # Loading — from pre-trained offline artifact
    # ------------------------------------------------------------------

    def _load_artifact(self) -> None:
        logger.info("Loading forecast model artifact from %s …", _ARTIFACT_PATH)
        if not os.path.exists(_ARTIFACT_PATH):
            raise FileNotFoundError(f"Forecast artifact not found at {_ARTIFACT_PATH}")
            
        state = joblib.load(_ARTIFACT_PATH)
        
        self._model = state["_model"]
        self._encoder = state["_encoder"]
        self._last_known_features = state["_last_known_features"]
        self._historical_means = state["_historical_means"]
        self._overall_train_mean = state["_overall_train_mean"]
        self._recent_history = state["_recent_history"]
        self._db_center_to_csv = state["_db_center_to_csv"]
        self._db_meal_to_csv = state["_db_meal_to_csv"]
        self._residual_pool = state["_residual_pool"]
        
        logger.info("Model artifact loaded successfully.")

    # ------------------------------------------------------------------
    # ID mapping helper
    # ------------------------------------------------------------------

    def map_ids(self, db_center_id: int, db_meal_id: int) -> tuple[int, int]:
        """Map DB center/meal IDs to representative CSV IDs."""
        self._ensure_trained()
        csv_cid = self._db_center_to_csv.get(
            db_center_id, list(self._db_center_to_csv.values())[0]
        )
        csv_mid = self._db_meal_to_csv.get(
            db_meal_id, list(self._db_meal_to_csv.values())[0]
        )
        return csv_cid, csv_mid

    def get_recent_history(self, db_center_id: int, db_meal_id: int) -> list[dict] | None:
        """Return the last 8 historical observations for the mapped centre-meal pair."""
        self._ensure_trained()
        csv_cid, csv_mid = self.map_ids(db_center_id, db_meal_id)
        return self._recent_history.get((csv_cid, csv_mid))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_forecast(
        self,
        center_id: int,
        meal_id: int,
        db: Session,
        target_date: date_type | None = None,
    ) -> Forecast:
        """Generate a demand forecast for a centre–meal pair.

        Uses the trained HistGradientBoosting model with the last known
        training-period features for the mapped CSV pair.  Confidence
        bounds come from the Experiment 2 residual pool (10th / 90th
        percentile of simulated demand).
        """
        self._ensure_trained()

        csv_cid, csv_mid = self.map_ids(center_id, meal_id)
        features = self._last_known_features.get((csv_cid, csv_mid))

        if features is None:
            # Fallback: use historical mean if pair not found
            hist_mean = self._historical_means.get(
                (csv_cid, csv_mid), self._overall_train_mean
            )
            point_forecast = float(hist_mean)
            conf_lower = point_forecast * 0.7
            conf_upper = point_forecast * 1.3
        else:
            # Build feature vector and predict
            cat_vals = [[features[f] for f in CATEGORICAL_FEATURES]]
            num_vals = [[features[f] for f in NUMERIC_FEATURES]]
            X_cat = self._encoder.transform(cat_vals)
            X = np.hstack([X_cat, np.array(num_vals, dtype=float)])
            point_forecast = float(max(0.0, self._model.predict(X)[0]))

            # Confidence bounds from residual-based simulation
            if self._residual_pool is not None:
                rng = np.random.default_rng(
                    abs(hash((center_id, meal_id))) % (2**31)
                )
                simulated = point_forecast + rng.choice(
                    self._residual_pool, size=1000, replace=True
                )
                simulated = np.maximum(0.0, simulated)
                conf_lower = float(np.percentile(simulated, 10))
                conf_upper = float(np.percentile(simulated, 90))
            else:
                conf_lower = point_forecast * 0.7
                conf_upper = point_forecast * 1.3

        forecast_date = target_date if target_date else date_type.today()

        forecast = Forecast(
            center_id=center_id,
            meal_id=meal_id,
            forecast_date=forecast_date,
            predicted_demand=round(point_forecast, 2),
            confidence_lower=round(conf_lower, 2),
            confidence_upper=round(conf_upper, 2),
            model_version="hgb-exp1-v1",
        )
        db.add(forecast)
        db.commit()
        db.refresh(forecast)
        return forecast

    def get_forecast(
        self, center_id: int, meal_id: int, db: Session
    ) -> Forecast | None:
        """Return the most recent forecast for a centre–meal pair."""
        return (
            db.query(Forecast)
            .filter(
                Forecast.center_id == center_id,
                Forecast.meal_id == meal_id,
            )
            .order_by(Forecast.created_at.desc())
            .first()
        )


# Module-level singleton
forecast_service = ForecastService()
