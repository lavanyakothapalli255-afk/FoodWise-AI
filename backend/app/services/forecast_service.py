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

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import OrdinalEncoder
from sqlalchemy.orm import Session

from app.models.db_models import Forecast

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths — resolved relative to this file, never modified
# ---------------------------------------------------------------------------
_SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SERVICE_DIR, "..", "..", ".."))
_TRAIN_CSV = os.path.join(
    _PROJECT_ROOT, "data", "extracted", "foodDemand_train", "train.csv"
)
_CENTER_CSV = os.path.join(
    _PROJECT_ROOT, "data", "extracted", "foodDemand_train", "fulfilment_center_info.csv"
)
_MEAL_CSV = os.path.join(
    _PROJECT_ROOT, "data", "extracted", "foodDemand_train", "meal_info.csv"
)
_RESIDUAL_CSV = os.path.join(
    _PROJECT_ROOT, "experiments", "experiment_2_validation_residuals.csv"
)

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
        """Train on first use so app startup remains fast."""
        if self._trained:
            return
        self._train()
        self._trained = True

    # ------------------------------------------------------------------
    # Training — mirrors Experiment 1 exactly
    # ------------------------------------------------------------------

    def _train(self) -> None:
        logger.info("Loading training data from %s …", _TRAIN_CSV)
        df = pd.read_csv(_TRAIN_CSV)
        center_info = pd.read_csv(_CENTER_CSV)
        meal_info = pd.read_csv(_MEAL_CSV)

        ml_df = df.merge(center_info, on="center_id", how="left")
        ml_df = ml_df.merge(meal_info, on="meal_id", how="left")

        # --- Feature engineering (Experiment 1, lines 99–121) ---
        ml_df["discount_ratio"] = (
            (ml_df["base_price"] - ml_df["checkout_price"]) / ml_df["base_price"]
        )
        ml_df["discount_ratio"] = ml_df["discount_ratio"].replace(
            [np.inf, -np.inf], np.nan
        )
        ml_df["week_mod_52"] = ml_df["week"] % 52
        ml_df["week_sin"] = np.sin(2 * np.pi * ml_df["week"] / 52.0)
        ml_df["week_cos"] = np.cos(2 * np.pi * ml_df["week"] / 52.0)

        # Frozen origin: hide test-period demand before computing lags
        ml_df["_demand_past"] = np.where(
            ml_df["week"] <= 135, ml_df["num_orders"], np.nan
        )
        ml_df = ml_df.sort_values(
            ["center_id", "meal_id", "week"]
        ).reset_index(drop=True)

        group_keys = ["center_id", "meal_id"]
        ml_df["lag_1"] = ml_df.groupby(group_keys)["_demand_past"].shift(1)
        ml_df["lag_2"] = ml_df.groupby(group_keys)["_demand_past"].shift(2)
        ml_df["lag_4"] = ml_df.groupby(group_keys)["_demand_past"].shift(4)
        ml_df["rolling_mean_4"] = ml_df.groupby(group_keys)["lag_1"].transform(
            lambda s: s.rolling(4, min_periods=1).mean()
        )
        ml_df["rolling_mean_8"] = ml_df.groupby(group_keys)["lag_1"].transform(
            lambda s: s.rolling(8, min_periods=1).mean()
        )
        lag_cols = ["lag_1", "lag_2", "lag_4", "rolling_mean_4", "rolling_mean_8"]
        ml_df[lag_cols] = ml_df.groupby(group_keys)[lag_cols].ffill()

        # --- Split (train on weeks ≤ 135 only) ---
        train_ml = ml_df[ml_df["week"] <= 135].copy()

        # --- Historical means per (center, meal) ---
        means = train_ml.groupby(group_keys)["num_orders"].mean()
        self._historical_means = means.to_dict()
        self._overall_train_mean = float(train_ml["num_orders"].mean())

        # --- Last-known feature row per pair (for prototype predictions) ---
        for (cid, mid), grp in train_ml.groupby(group_keys):
            last = grp.iloc[-1]
            self._last_known_features[(cid, mid)] = {
                f: last[f] for f in CATEGORICAL_FEATURES + NUMERIC_FEATURES
            }
            # Store last 8 historical actuals for context UI
            recent_grp = grp.tail(8)
            self._recent_history[(cid, mid)] = [
                {"week": int(row["week"]), "num_orders": int(row["num_orders"])}
                for _, row in recent_grp.iterrows()
            ]

        # --- Prototype mapping: DB IDs → representative CSV IDs ---
        csv_centers = sorted(train_ml["center_id"].unique())
        csv_meals = sorted(train_ml["meal_id"].unique())
        for db_id in range(1, 200):
            self._db_center_to_csv[db_id] = int(
                csv_centers[(db_id - 1) % len(csv_centers)]
            )
            self._db_meal_to_csv[db_id] = int(
                csv_meals[(db_id - 1) % len(csv_meals)]
            )

        # --- Encode categoricals and train (Experiment 1, lines 158–176) ---
        categorical_indices = list(range(len(CATEGORICAL_FEATURES)))
        self._encoder = OrdinalEncoder(
            handle_unknown="use_encoded_value",
            unknown_value=np.nan,
        )
        X_train_cat = self._encoder.fit_transform(
            train_ml[CATEGORICAL_FEATURES]
        )
        X_train = np.hstack(
            [X_train_cat, train_ml[NUMERIC_FEATURES].to_numpy()]
        )
        y_train = train_ml["num_orders"].to_numpy()

        self._model = HistGradientBoostingRegressor(
            random_state=42,
            categorical_features=categorical_indices,
        )
        logger.info(
            "Training HistGradientBoosting on %d rows …", len(X_train)
        )
        self._model.fit(X_train, y_train)
        logger.info("Model trained successfully.")

        # --- Residual pool for confidence bounds (Experiment 2) ---
        if os.path.exists(_RESIDUAL_CSV):
            residuals_df = pd.read_csv(_RESIDUAL_CSV)
            self._residual_pool = residuals_df["residual"].to_numpy()
            logger.info(
                "Loaded %d OOS residuals for confidence bounds.",
                len(self._residual_pool),
            )

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
