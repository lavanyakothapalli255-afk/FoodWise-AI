import pandas as pd
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import OrdinalEncoder

# Load the training dataset
df = pd.read_csv("data/extracted/foodDemand_train/train.csv")

# 1. First 5 rows
print("First 5 rows:")
print(df.head())

# 2. Shape of the dataset (rows, columns)
print("\nShape of the dataset:")
print(df.shape)

# 3. Column names
print("\nColumn names:")
print(df.columns)

# 4. Data types
print("\nData types:")
print(df.dtypes)

# 5. Missing values in each column
print("\nMissing values:")
print(df.isnull().sum())

# 6. Minimum and maximum week
print("\nMinimum week:")
print(df["week"].min())
print("Maximum week:")
print(df["week"].max())

# 7. Unique fulfillment centers
print("\nNumber of unique center_id values:")
print(df["center_id"].nunique())

# 8. Unique meals
print("\nNumber of unique meal_id values:")
print(df["meal_id"].nunique())

# -------------------------------------------------
# Experiment 1 baseline (historical mean)
# Training weeks: 1-135
# Test weeks: 136-145
# -------------------------------------------------

# Split by week. Test weeks are not used to calculate the mean.
train = df[df["week"] <= 135]
test = df[(df["week"] >= 136) & (df["week"] <= 145)]

# Mean num_orders for each center + meal, using training weeks only
baseline_means = (
    train.groupby(["center_id", "meal_id"])["num_orders"]
    .mean()
    .reset_index()
    .rename(columns={"num_orders": "predicted_orders"})
)

# Attach those training means to the matching test rows
test_with_predictions = test.merge(
    baseline_means,
    on=["center_id", "meal_id"],
    how="left",
)

# If a center+meal never appeared in training, use the overall training mean
overall_train_mean = train["num_orders"].mean()
test_with_predictions["predicted_orders"] = test_with_predictions[
    "predicted_orders"
].fillna(overall_train_mean)

# Compare actual test orders with the baseline predictions
y_true = test_with_predictions["num_orders"]
y_pred = test_with_predictions["predicted_orders"]

mae = mean_absolute_error(y_true, y_pred)
rmse = np.sqrt(mean_squared_error(y_true, y_pred))

print("\nBaseline Results")
print("MAE:", mae)
print("RMSE:", rmse)

# -------------------------------------------------
# Experiment 1 ML model (HistGradientBoosting)
# Same split: train weeks 1-135, test weeks 136-145
# Frozen origin: lag/rolling features never use
# actual num_orders from weeks 136-145
# -------------------------------------------------

center_info = pd.read_csv("data/extracted/foodDemand_train/fulfilment_center_info.csv")
meal_info = pd.read_csv("data/extracted/foodDemand_train/meal_info.csv")

ml_df = df.merge(center_info, on="center_id", how="left")
ml_df = ml_df.merge(meal_info, on="meal_id", how="left")

# Price discount compared with the listed base price
ml_df["discount_ratio"] = (ml_df["base_price"] - ml_df["checkout_price"]) / ml_df["base_price"]
ml_df["discount_ratio"] = ml_df["discount_ratio"].replace([np.inf, -np.inf], np.nan)

# Time features from the week index (no calendar dates in this dataset)
ml_df["week_mod_52"] = ml_df["week"] % 52
ml_df["week_sin"] = np.sin(2 * np.pi * ml_df["week"] / 52.0)
ml_df["week_cos"] = np.cos(2 * np.pi * ml_df["week"] / 52.0)

# Hide test-period demand before building lags/rollings
ml_df["_demand_past"] = np.where(ml_df["week"] <= 135, ml_df["num_orders"], np.nan)
ml_df = ml_df.sort_values(["center_id", "meal_id", "week"]).reset_index(drop=True)

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

# Reuse the last known train-period lag/rolling values for later test weeks
lag_cols = ["lag_1", "lag_2", "lag_4", "rolling_mean_4", "rolling_mean_8"]
ml_df[lag_cols] = ml_df.groupby(group_keys)[lag_cols].ffill()

train_ml = ml_df[ml_df["week"] <= 135].copy()
test_ml = ml_df[(ml_df["week"] >= 136) & (ml_df["week"] <= 145)].copy()

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

# Convert categories to integer codes. Fit on training weeks only.
encoder = OrdinalEncoder(
    handle_unknown="use_encoded_value",
    unknown_value=np.nan,
)
X_train_cat = encoder.fit_transform(train_ml[categorical_features])
X_test_cat = encoder.transform(test_ml[categorical_features])

X_train = np.hstack([X_train_cat, train_ml[numeric_features].to_numpy()])
X_test = np.hstack([X_test_cat, test_ml[numeric_features].to_numpy()])
y_train = train_ml["num_orders"].to_numpy()
y_test = test_ml["num_orders"].to_numpy()

categorical_indices = list(range(len(categorical_features)))

ml_model = HistGradientBoostingRegressor(
    random_state=42,
    categorical_features=categorical_indices,
)
ml_model.fit(X_train, y_train)
ml_pred = ml_model.predict(X_test)

ml_mae = mean_absolute_error(y_test, ml_pred)
ml_rmse = np.sqrt(mean_squared_error(y_test, ml_pred))
mae_improvement = mae - ml_mae
rmse_improvement = rmse - ml_rmse

print("\nML Results")
print("ML MAE:", ml_mae)
print("ML RMSE:", ml_rmse)
print("Baseline MAE:", mae)
print("Baseline RMSE:", rmse)
print("MAE improvement vs baseline:", mae_improvement)
print("RMSE improvement vs baseline:", rmse_improvement)
