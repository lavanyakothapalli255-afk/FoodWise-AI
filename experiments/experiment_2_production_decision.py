import pandas as pd
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import OrdinalEncoder

# -------------------------------------------------
# Experiment 2: Adaptive Production Decision
# Stages A–B: causal features + walk-forward OOS residuals
#   (weeks 116–135). Weeks 136–145 are not used there.
# Stages C–D: frozen-origin test forecasts, residual-based
#   demand scenarios, production policies, then test evaluation.
# -------------------------------------------------

df = pd.read_csv("data/extracted/foodDemand_train/train.csv")
center_info = pd.read_csv("data/extracted/foodDemand_train/fulfilment_center_info.csv")
meal_info = pd.read_csv("data/extracted/foodDemand_train/meal_info.csv")

# Stage A: feature engineering on weeks 1–135 only
ml_df = df[df["week"] <= 135].copy()
ml_df = ml_df.merge(center_info, on="center_id", how="left")
ml_df = ml_df.merge(meal_info, on="meal_id", how="left")

ml_df["discount_ratio"] = (ml_df["base_price"] - ml_df["checkout_price"]) / ml_df["base_price"]
ml_df["discount_ratio"] = ml_df["discount_ratio"].replace([np.inf, -np.inf], np.nan)

ml_df["week_mod_52"] = ml_df["week"] % 52
ml_df["week_sin"] = np.sin(2 * np.pi * ml_df["week"] / 52.0)
ml_df["week_cos"] = np.cos(2 * np.pi * ml_df["week"] / 52.0)

ml_df = ml_df.sort_values(["center_id", "meal_id", "week"]).reset_index(drop=True)

group_keys = ["center_id", "meal_id"]
# Shifted demand: week t uses actual orders only through week t-1
ml_df["lag_1"] = ml_df.groupby(group_keys)["num_orders"].shift(1)
ml_df["lag_2"] = ml_df.groupby(group_keys)["num_orders"].shift(2)
ml_df["lag_4"] = ml_df.groupby(group_keys)["num_orders"].shift(4)
ml_df["rolling_mean_4"] = ml_df.groupby(group_keys)["lag_1"].transform(
    lambda s: s.rolling(4, min_periods=1).mean()
)
ml_df["rolling_mean_8"] = ml_df.groupby(group_keys)["lag_1"].transform(
    lambda s: s.rolling(8, min_periods=1).mean()
)

categorical_features = [
    "center_id",
    "meal_id",
    "center_type",
    "city_code",
    "region_code",
    "category",
    "cuisine",
]
numeric_features = [
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
categorical_indices = list(range(len(categorical_features)))

# Stage B: one-step-ahead walk-forward on weeks 116–135
validation_weeks = list(range(116, 136))
residual_frames = []

for t in validation_weeks:
    train_fold = ml_df[ml_df["week"] < t]
    predict_fold = ml_df[ml_df["week"] == t].copy()

    encoder = OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=np.nan,
    )
    X_train_cat = encoder.fit_transform(train_fold[categorical_features])
    X_pred_cat = encoder.transform(predict_fold[categorical_features])

    X_train = np.hstack([X_train_cat, train_fold[numeric_features].to_numpy()])
    X_pred = np.hstack([X_pred_cat, predict_fold[numeric_features].to_numpy()])
    y_train = train_fold["num_orders"].to_numpy()

    model = HistGradientBoostingRegressor(
        random_state=42,
        categorical_features=categorical_indices,
    )
    model.fit(X_train, y_train)
    predicted = model.predict(X_pred)

    actual = predict_fold["num_orders"].to_numpy()
    residual = actual - predicted
    relative_error = np.where(actual != 0, residual / actual, np.nan)

    fold_residuals = pd.DataFrame(
        {
            "center_id": predict_fold["center_id"].to_numpy(),
            "meal_id": predict_fold["meal_id"].to_numpy(),
            "week": predict_fold["week"].to_numpy(),
            "actual": actual,
            "predicted": predicted,
            "residual": residual,
            "relative_error": relative_error,
        }
    )
    residual_frames.append(fold_residuals)
    print(f"Processed validation week {t}: {len(fold_residuals)} OOS rows")

residuals = pd.concat(residual_frames, ignore_index=True)

mae = mean_absolute_error(residuals["actual"], residuals["predicted"])
rmse = np.sqrt(mean_squared_error(residuals["actual"], residuals["predicted"]))

print("\nValidation weeks processed:", residuals["week"].nunique())
print("Number of OOS residuals:", len(residuals))
print("Validation MAE:", mae)
print("Validation RMSE:", rmse)
print("Residual mean:", residuals["residual"].mean())
print("Residual median:", residuals["residual"].median())
print("Residual std:", residuals["residual"].std())
print("Residual 5th percentile:", residuals["residual"].quantile(0.05))
print("Residual 95th percentile:", residuals["residual"].quantile(0.95))

output_path = "experiments/experiment_2_validation_residuals.csv"
residuals.to_csv(output_path, index=False)
print("Saved residual table to:", output_path)

# -------------------------------------------------
# Stage D: Experiment 1 frozen-origin forecasts for weeks 136–145
# Trained on weeks 1–135. Test demand is never used in features.
# -------------------------------------------------

ml_full = df.merge(center_info, on="center_id", how="left")
ml_full = ml_full.merge(meal_info, on="meal_id", how="left")

ml_full["discount_ratio"] = (ml_full["base_price"] - ml_full["checkout_price"]) / ml_full["base_price"]
ml_full["discount_ratio"] = ml_full["discount_ratio"].replace([np.inf, -np.inf], np.nan)
ml_full["week_mod_52"] = ml_full["week"] % 52
ml_full["week_sin"] = np.sin(2 * np.pi * ml_full["week"] / 52.0)
ml_full["week_cos"] = np.cos(2 * np.pi * ml_full["week"] / 52.0)

ml_full["_demand_past"] = np.where(ml_full["week"] <= 135, ml_full["num_orders"], np.nan)
ml_full = ml_full.sort_values(["center_id", "meal_id", "week"]).reset_index(drop=True)

ml_full["lag_1"] = ml_full.groupby(group_keys)["_demand_past"].shift(1)
ml_full["lag_2"] = ml_full.groupby(group_keys)["_demand_past"].shift(2)
ml_full["lag_4"] = ml_full.groupby(group_keys)["_demand_past"].shift(4)
ml_full["rolling_mean_4"] = ml_full.groupby(group_keys)["lag_1"].transform(
    lambda s: s.rolling(4, min_periods=1).mean()
)
ml_full["rolling_mean_8"] = ml_full.groupby(group_keys)["lag_1"].transform(
    lambda s: s.rolling(8, min_periods=1).mean()
)
lag_cols = ["lag_1", "lag_2", "lag_4", "rolling_mean_4", "rolling_mean_8"]
ml_full[lag_cols] = ml_full.groupby(group_keys)[lag_cols].ffill()

train_final = ml_full[ml_full["week"] <= 135].copy()
test_final = ml_full[(ml_full["week"] >= 136) & (ml_full["week"] <= 145)].copy()

encoder_final = OrdinalEncoder(
    handle_unknown="use_encoded_value",
    unknown_value=np.nan,
)
X_train_final_cat = encoder_final.fit_transform(train_final[categorical_features])
X_test_final_cat = encoder_final.transform(test_final[categorical_features])
X_train_final = np.hstack([X_train_final_cat, train_final[numeric_features].to_numpy()])
X_test_final = np.hstack([X_test_final_cat, test_final[numeric_features].to_numpy()])
y_train_final = train_final["num_orders"].to_numpy()

final_model = HistGradientBoostingRegressor(
    random_state=42,
    categorical_features=categorical_indices,
)
final_model.fit(X_train_final, y_train_final)
test_final = test_final.copy()
test_final["point_forecast"] = final_model.predict(X_test_final)

print("\nStage D test rows:", len(test_final))
print("Stage D weeks:", int(test_final["week"].min()), "-", int(test_final["week"].max()))

# -------------------------------------------------
# Stage C: residual-based demand scenarios and production policies
# Residual pool and ŷ only. Test actuals are not used to set Q.
# -------------------------------------------------

residual_pool_df = pd.read_csv(output_path)
residual_pool = residual_pool_df["residual"].to_numpy()

center_meal_means = (
    train_final.groupby(["center_id", "meal_id"])["num_orders"]
    .mean()
    .reset_index()
    .rename(columns={"num_orders": "q_historical_mean"})
)
overall_train_mean = train_final["num_orders"].mean()
test_final = test_final.merge(center_meal_means, on=["center_id", "meal_id"], how="left")
test_final["q_historical_mean"] = test_final["q_historical_mean"].fillna(overall_train_mean)

n_samples = 1000
rng = np.random.default_rng(42)
n_test = len(test_final)
y_hat = test_final["point_forecast"].to_numpy()
sampled_residuals = rng.choice(residual_pool, size=(n_test, n_samples), replace=True)
d_sim = np.maximum(0.0, y_hat[:, np.newaxis] + sampled_residuals)

policies = {
    "historical_mean": test_final["q_historical_mean"].to_numpy(),
    "p50": np.maximum(0.0, y_hat),
    "p70": np.percentile(d_sim, 70, axis=1),
    "p80": np.percentile(d_sim, 80, axis=1),
    "p90": np.percentile(d_sim, 90, axis=1),
    "p95": np.percentile(d_sim, 95, axis=1),
}

expected_surplus = {}
expected_shortage = {}
for name, q in policies.items():
    surplus_sim = np.maximum(q[:, np.newaxis] - d_sim, 0.0)
    shortage_sim = np.maximum(d_sim - q[:, np.newaxis], 0.0)
    expected_surplus[name] = surplus_sim.mean(axis=1)
    expected_shortage[name] = shortage_sim.mean(axis=1)

# Policies are now frozen. Actual test demand is used only below.
actual_demand = test_final["num_orders"].to_numpy()
total_actual = actual_demand.sum()

realized_surplus = {}
realized_shortage = {}
for name, q in policies.items():
    realized_surplus[name] = np.maximum(q - actual_demand, 0.0)
    realized_shortage[name] = np.maximum(actual_demand - q, 0.0)

summary_rows = []
for name, q in policies.items():
    surplus = realized_surplus[name]
    shortage = realized_shortage[name]
    fill_rate = 1.0 - shortage.sum() / total_actual
    cycle_service_level = np.mean(q >= actual_demand)
    summary_rows.append(
        {
            "policy": name,
            "expected_surplus_mean": expected_surplus[name].mean(),
            "expected_shortage_mean": expected_shortage[name].mean(),
            "expected_surplus_total": expected_surplus[name].sum(),
            "expected_shortage_total": expected_shortage[name].sum(),
            "surplus_mean": surplus.mean(),
            "shortage_mean": shortage.mean(),
            "surplus_total": surplus.sum(),
            "shortage_total": shortage.sum(),
            "fill_rate": fill_rate,
            "cycle_service_level": cycle_service_level,
        }
    )

summary = pd.DataFrame(summary_rows)
print("\nPolicy comparison")
print(summary.to_string(index=False))

results = pd.DataFrame(
    {
        "center_id": test_final["center_id"].to_numpy(),
        "meal_id": test_final["meal_id"].to_numpy(),
        "week": test_final["week"].to_numpy(),
        "actual_demand": actual_demand,
        "point_forecast": y_hat,
    }
)
for name, q in policies.items():
    results[f"q_{name}"] = q
    results[f"surplus_{name}"] = realized_surplus[name]
    results[f"shortage_{name}"] = realized_shortage[name]

results_path = "experiments/experiment_2_policy_results.csv"
results.to_csv(results_path, index=False)
print("Saved policy results to:", results_path)
