import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.services.forecast_service import forecast_service

class MockDB:
    def add(self, obj): pass
    def commit(self): pass
    def refresh(self, obj): pass

def main():
    print("Testing generate_forecast with artifact loading...")
    forecast = forecast_service.generate_forecast(1, 1, MockDB())
    print(f"Result: {forecast.predicted_demand} (Lower: {forecast.confidence_lower}, Upper: {forecast.confidence_upper})")

if __name__ == "__main__":
    main()
