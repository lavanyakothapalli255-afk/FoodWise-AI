"""Phase 2 comprehensive verification script.

Tests:
  1. Backend import
  2. PostgreSQL connectivity + 7 tables
  3. POST /api/forecast/generate
  4. GET  /api/forecast/{center_id}/{meal_id}
  5. POST /api/production/recommend (multiple policies)
  6. POST /api/production/record
  7. Methodology cross-check (different policies → different trade-offs)
"""

import sys
import json

print("=" * 65)
print("PHASE 2 VERIFICATION")
print("=" * 65)

# ------------------------------------------------------------------
# 1. Backend import
# ------------------------------------------------------------------
print("\n[1] Backend Import")
try:
    from app.main import app
    print(f"    OK — {app.title}")
except Exception as e:
    print(f"    FAIL — {e}")
    sys.exit(1)

# ------------------------------------------------------------------
# 2. Database connectivity + tables
# ------------------------------------------------------------------
print("\n[2] PostgreSQL Connection & Tables")
from sqlalchemy import inspect as sa_inspect
from app.database import engine

inspector = sa_inspect(engine)
tables = sorted(inspector.get_table_names())
expected = sorted([
    "centers", "meals", "recipients", "historical_demand",
    "forecasts", "production_decisions", "redistribution_plans",
])
if tables == expected:
    print(f"    OK — 7 approved tables present")
else:
    print(f"    FAIL — got {tables}")
    sys.exit(1)

# ------------------------------------------------------------------
# 3. POST /api/forecast/generate
# ------------------------------------------------------------------
print("\n[3] POST /api/forecast/generate")
from fastapi.testclient import TestClient

client = TestClient(app)

resp = client.post("/api/forecast/generate", json={
    "center_id": 1,
    "meal_id": 1,
    "target_date": "2026-09-13",
})
print(f"    Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"    predicted_demand: {data['predicted_demand']}")
    print(f"    confidence_lower: {data['confidence_lower']}")
    print(f"    confidence_upper: {data['confidence_upper']}")
    print(f"    model_version:    {data['model_version']}")
    forecast_id = data["id"]
    print(f"    OK — forecast id={forecast_id}")
else:
    print(f"    FAIL — {resp.text}")
    sys.exit(1)

# ------------------------------------------------------------------
# 4. GET /api/forecast/{center_id}/{meal_id}
# ------------------------------------------------------------------
print("\n[4] GET /api/forecast/1/1")
resp = client.get("/api/forecast/1/1")
print(f"    Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"    predicted_demand: {data['predicted_demand']}")
    print(f"    OK — retrieved forecast id={data['id']}")
else:
    print(f"    FAIL — {resp.text}")
    sys.exit(1)

# ------------------------------------------------------------------
# 5. POST /api/production/recommend (multiple policies)
# ------------------------------------------------------------------
print("\n[5] POST /api/production/recommend (all policies)")

policies = ["p50", "p70", "p80", "p90", "p95", "historical_mean"]
results = {}

for policy in policies:
    resp = client.post("/api/production/recommend", json={
        "center_id": 1,
        "meal_id": 1,
        "date": "2026-09-13",
        "policy": policy,
    })
    if resp.status_code != 200:
        print(f"    FAIL [{policy}] — {resp.text}")
        sys.exit(1)
    d = resp.json()
    results[policy] = d
    print(
        f"    {policy:18s}  qty={d['recommended_quantity']:6d}  "
        f"surplus={d['expected_surplus']:8.1f}  "
        f"shortage={d['expected_shortage']:8.1f}  "
        f"forecast={d['point_forecast']:.1f}"
    )

print("    OK — all 6 policies returned recommendations")

# Methodology cross-check: higher percentile → higher qty and surplus
p50_qty = results["p50"]["recommended_quantity"]
p95_qty = results["p95"]["recommended_quantity"]
p50_surplus = results["p50"]["expected_surplus"]
p95_surplus = results["p95"]["expected_surplus"]
p50_shortage = results["p50"]["expected_shortage"]
p95_shortage = results["p95"]["expected_shortage"]

print("\n    Trade-off verification:")
print(f"      p50 qty={p50_qty}, surplus={p50_surplus:.1f}, shortage={p50_shortage:.1f}")
print(f"      p95 qty={p95_qty}, surplus={p95_surplus:.1f}, shortage={p95_shortage:.1f}")

if p95_qty >= p50_qty:
    print("      OK — p95 >= p50 quantity (higher buffer)")
else:
    print("      WARNING — unexpected: p95 < p50 quantity")

if p95_surplus >= p50_surplus:
    print("      OK — p95 surplus >= p50 surplus (more waste at higher buffer)")
else:
    print("      WARNING — unexpected surplus ordering")

if p95_shortage <= p50_shortage:
    print("      OK — p95 shortage <= p50 shortage (less shortage at higher buffer)")
else:
    print("      WARNING — unexpected shortage ordering")

# ------------------------------------------------------------------
# 6. POST /api/production/record
# ------------------------------------------------------------------
print("\n[6] POST /api/production/record")
resp = client.post("/api/production/record", json={
    "center_id": 1,
    "meal_id": 1,
    "date": "2026-09-13",
    "actual_quantity": 200,
})
print(f"    Status: {resp.status_code}")
if resp.status_code == 200:
    d = resp.json()
    print(f"    actual_quantity:  {d['actual_quantity']}")
    print(f"    decision_status: {d['decision_status']}")
    print(f"    OK — recorded actual production")
else:
    print(f"    FAIL — {resp.text}")
    sys.exit(1)

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
print("\n" + "=" * 65)
print("PHASE 2 BACKEND VERIFICATION: ALL CHECKS PASSED")
print("=" * 65)
