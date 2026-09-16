import os
import sys
import joblib
from datetime import date

# Ensure backend root is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.forecast_service import ForecastService

# Mock DB session for testing equivalence
class MockDB:
    def add(self, obj): pass
    def commit(self): pass
    def refresh(self, obj): pass

def main():
    print("Initializing original ForecastService...")
    original_service = ForecastService()
    
    print("Generating baseline forecast (will trigger training)...")
    db_mock = MockDB()
    baseline = original_service.generate_forecast(1, 1, db_mock, target_date=date(2023, 1, 1))
    print(f"Baseline Forecast: {baseline.predicted_demand} (lower: {baseline.confidence_lower}, upper: {baseline.confidence_upper})")
    
    print("Extracting state into dictionary...")
    state = {
        "_model": original_service._model,
        "_encoder": original_service._encoder,
        "_last_known_features": original_service._last_known_features,
        "_historical_means": original_service._historical_means,
        "_overall_train_mean": original_service._overall_train_mean,
        "_recent_history": original_service._recent_history,
        "_db_center_to_csv": original_service._db_center_to_csv,
        "_db_meal_to_csv": original_service._db_meal_to_csv,
        "_residual_pool": original_service._residual_pool,
    }
    
    artifact_dir = os.path.join(os.path.dirname(__file__), '..', 'artifacts')
    os.makedirs(artifact_dir, exist_ok=True)
    artifact_path = os.path.join(artifact_dir, 'forecast_model_v1.joblib')
    
    print(f"Saving state to {artifact_path}...")
    joblib.dump(state, artifact_path, compress=3)
    
    print("Loading state into new service instance...")
    loaded_state = joblib.load(artifact_path)
    
    new_service = ForecastService()
    new_service._model = loaded_state["_model"]
    new_service._encoder = loaded_state["_encoder"]
    new_service._last_known_features = loaded_state["_last_known_features"]
    new_service._historical_means = loaded_state["_historical_means"]
    new_service._overall_train_mean = loaded_state["_overall_train_mean"]
    new_service._recent_history = loaded_state["_recent_history"]
    new_service._db_center_to_csv = loaded_state["_db_center_to_csv"]
    new_service._db_meal_to_csv = loaded_state["_db_meal_to_csv"]
    new_service._residual_pool = loaded_state["_residual_pool"]
    new_service._trained = True  # Prevent training
    
    print("Generating forecast from loaded artifact...")
    new_forecast = new_service.generate_forecast(1, 1, db_mock, target_date=date(2023, 1, 1))
    print(f"Loaded Forecast: {new_forecast.predicted_demand} (lower: {new_forecast.confidence_lower}, upper: {new_forecast.confidence_upper})")
    
    assert baseline.predicted_demand == new_forecast.predicted_demand, "Point forecast mismatch!"
    assert baseline.confidence_lower == new_forecast.confidence_lower, "Confidence lower mismatch!"
    assert baseline.confidence_upper == new_forecast.confidence_upper, "Confidence upper mismatch!"
    
    print("Equivalence test PASSED!")
    
    size_mb = os.path.getsize(artifact_path) / (1024 * 1024)
    print(f"Artifact size: {size_mb:.2f} MB")

if __name__ == "__main__":
    main()
