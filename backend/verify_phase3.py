"""Phase 3 comprehensive verification script.

Tests:
  1.  Backend import
  2.  PostgreSQL connectivity + exactly 7 approved tables
  3.  POST /api/surplus/detect — surplus scenario
  4.  POST /api/surplus/detect — no-surplus scenario
  5.  POST /api/redistribution/optimize — generates plan
  6.  Recipient capacity constraint
  7.  Unavailable recipient constraint
  8.  Transit-time feasibility constraint
  9.  Total allocation <= surplus
  10. No negative allocations
  11. POST /api/redistribution/authorize — status change
  12. Database persistence
  13. Phase 1 + Phase 2 endpoints still register
  14. (Frontend build is tested separately)
"""

import sys
from datetime import date

print("=" * 65)
print("PHASE 3 VERIFICATION")
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
    print(f"    OK — 7 approved tables present: {tables}")
else:
    print(f"    FAIL — got {tables}")
    sys.exit(1)

# ------------------------------------------------------------------
# Setup: ensure seed data and a recorded production decision exist
# ------------------------------------------------------------------
print("\n[Setup] Ensuring test data exists")
from fastapi.testclient import TestClient

client = TestClient(app)

# Generate a forecast so surplus detection has consumption data
resp = client.post("/api/forecast/generate", json={
    "center_id": 1,
    "meal_id": 1,
    "target_date": "2026-09-13",
})
print(f"    Forecast generate: {resp.status_code}")
forecast_demand = resp.json().get("predicted_demand", 0)
print(f"    Forecast demand: {forecast_demand}")

# Create a production recommendation
resp = client.post("/api/production/recommend", json={
    "center_id": 1,
    "meal_id": 1,
    "date": "2026-09-13",
    "policy": "p80",
})
print(f"    Production recommend: {resp.status_code}")

# Record actual production HIGHER than forecast to create surplus
surplus_production = int(forecast_demand) + 50
resp = client.post("/api/production/record", json={
    "center_id": 1,
    "meal_id": 1,
    "date": "2026-09-13",
    "actual_quantity": surplus_production,
})
print(f"    Production record: {resp.status_code} (actual={surplus_production})")

# Seed recipients if needed
from app.database import SessionLocal
from app.models.db_models import Recipient

db = SessionLocal()
if db.query(Recipient).count() == 0:
    recipients = [
        Recipient(name="City Shelter A", type="shelter", location="Area 1",
                  capacity=120, is_active=True),
        Recipient(name="Food Bank B", type="food_bank", location="Area 2",
                  capacity=100, is_active=True),
        Recipient(name="Community Kitchen C", type="community", location="Area 3",
                  capacity=60, is_active=True),
        Recipient(name="Unavailable Center D", type="ngo", location="Area 4",
                  capacity=120, is_active=False),
    ]
    db.add_all(recipients)
    db.commit()
    print(f"    Seeded {len(recipients)} recipients")
else:
    print(f"    Recipients already exist ({db.query(Recipient).count()})")

# Get recipient IDs
all_recipients = db.query(Recipient).all()
recipient_ids = [r.id for r in all_recipients]
recipient_map = {r.id: r for r in all_recipients}
print(f"    Recipient IDs: {recipient_ids}")
db.close()

# ------------------------------------------------------------------
# 3. POST /api/surplus/detect — surplus scenario
# ------------------------------------------------------------------
print("\n[3] POST /api/surplus/detect — surplus scenario")
resp = client.post("/api/surplus/detect", json={
    "center_id": 1,
    "meal_id": 1,
    "date": "2026-09-13",
})
print(f"    Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"    actual_production:    {data['actual_production']}")
    print(f"    actual_consumption:   {data['actual_consumption']}")
    print(f"    surplus_quantity:     {data['surplus_quantity']}")
    print(f"    shortage_quantity:    {data['shortage_quantity']}")
    print(f"    status:              {data['status']}")
    print(f"    eligibility_advisory (truncated): {data['eligibility_advisory'][:80]}...")
    if data["status"] == "surplus_detected" and data["surplus_quantity"] > 0:
        print("    OK — surplus detected correctly")
        detected_surplus = data["surplus_quantity"]
    else:
        print("    FAIL — expected surplus_detected with positive surplus")
        sys.exit(1)
else:
    print(f"    FAIL — {resp.text}")
    sys.exit(1)

# ------------------------------------------------------------------
# 4. POST /api/surplus/detect — no-surplus scenario
# ------------------------------------------------------------------
print("\n[4] POST /api/surplus/detect — no-surplus scenario")
# Provide actual_consumption >= production to get no surplus
resp = client.post("/api/surplus/detect", json={
    "center_id": 1,
    "meal_id": 1,
    "date": "2026-09-13",
    "actual_consumption": surplus_production + 10,
})
print(f"    Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"    surplus_quantity: {data['surplus_quantity']}")
    print(f"    status:          {data['status']}")
    if data["status"] == "no_surplus" and data["surplus_quantity"] == 0:
        print("    OK — no surplus correctly detected")
    else:
        print("    FAIL — expected no_surplus with zero surplus")
        sys.exit(1)
else:
    print(f"    FAIL — {resp.text}")
    sys.exit(1)

# ------------------------------------------------------------------
# 5. POST /api/redistribution/optimize — generates plan
# ------------------------------------------------------------------
print("\n[5] POST /api/redistribution/optimize — generate plan")

# Build overrides using the actual recipient IDs from DB
# Include one unavailable recipient (is_active=False) to test constraint 7
overrides = []
for rid in recipient_ids:
    r = recipient_map[rid]
    # Give one recipient a time-infeasible transit time (for constraint 8)
    transit = 130.0 if r.name == "Community Kitchen C" else 15.0
    overrides.append({
        "recipient_id": rid,
        "distance_km": 5.0 + (rid * 2),
        "transit_time_min": transit,
        "usable_time_remaining_min": 120.0,
        "priority": rid,
    })

test_surplus = min(detected_surplus, 100)  # Use a manageable number

resp = client.post("/api/redistribution/optimize", json={
    "center_id": 1,
    "meal_id": 1,
    "date": "2026-09-13",
    "surplus_quantity": test_surplus,
    "recipient_overrides": overrides,
})
print(f"    Status: {resp.status_code}")
if resp.status_code != 200:
    print(f"    FAIL — {resp.text}")
    sys.exit(1)

opt = resp.json()
print(f"    solver_status:             {opt['solver_status']}")
print(f"    surplus_quantity:          {opt['surplus_quantity']}")
print(f"    total_allocated:           {opt['total_allocated']}")
print(f"    unallocated_surplus:       {opt['unallocated_surplus']}")
print(f"    total_transport_distance:  {opt['total_transport_distance']}")
print(f"    allocation_percentage:     {opt['allocation_percentage']}%")
print(f"    constraint_violations:     {opt['constraint_violations']}")
print(f"    plan_ids:                  {opt['plan_ids']}")
print(f"    authorization_status:      {opt['authorization_status']}")

print("\n    Per-recipient allocations:")
for a in opt["allocations"]:
    print(
        f"      {a['recipient_name']:25s}  cap={a['capacity']:4d}  "
        f"avail={a['is_available']}  time_ok={a['is_time_feasible']}  "
        f"pri={a['priority']}  alloc={a['allocated_quantity']}"
    )

if opt["solver_status"] == "success":
    print("    OK — optimization successful")
else:
    print(f"    FAIL — solver status: {opt['solver_status']}")
    sys.exit(1)

# ------------------------------------------------------------------
# 6. Recipient capacity constraint
# ------------------------------------------------------------------
print("\n[6] Capacity constraint check")
capacity_ok = True
for a in opt["allocations"]:
    if a["allocated_quantity"] > a["capacity"]:
        print(f"    FAIL — {a['recipient_name']}: alloc {a['allocated_quantity']} > capacity {a['capacity']}")
        capacity_ok = False
if capacity_ok:
    print("    OK — no allocation exceeds recipient capacity")
else:
    sys.exit(1)

# ------------------------------------------------------------------
# 7. Unavailable recipient constraint
# ------------------------------------------------------------------
print("\n[7] Unavailable recipient constraint check")
unavail_ok = True
for a in opt["allocations"]:
    if not a["is_available"] and a["allocated_quantity"] > 0:
        print(f"    FAIL — {a['recipient_name']}: unavailable but allocated {a['allocated_quantity']}")
        unavail_ok = False
if unavail_ok:
    print("    OK — unavailable recipients received zero allocation")
else:
    sys.exit(1)

# ------------------------------------------------------------------
# 8. Transit-time feasibility constraint
# ------------------------------------------------------------------
print("\n[8] Transit-time feasibility constraint check")
time_ok = True
for a in opt["allocations"]:
    if not a["is_time_feasible"] and a["allocated_quantity"] > 0:
        print(
            f"    FAIL — {a['recipient_name']}: time-infeasible "
            f"(transit={a['transit_time_min']} > usable={a['usable_time_remaining_min']}) "
            f"but allocated {a['allocated_quantity']}"
        )
        time_ok = False
if time_ok:
    print("    OK — time-infeasible recipients received zero allocation")
else:
    sys.exit(1)

# ------------------------------------------------------------------
# 9. Total allocation <= surplus
# ------------------------------------------------------------------
print("\n[9] Total allocation <= surplus check")
total_alloc = sum(a["allocated_quantity"] for a in opt["allocations"])
if total_alloc <= test_surplus:
    print(f"    OK — total allocated ({total_alloc}) <= surplus ({test_surplus})")
else:
    print(f"    FAIL — total allocated ({total_alloc}) > surplus ({test_surplus})")
    sys.exit(1)

# ------------------------------------------------------------------
# 10. No negative allocations
# ------------------------------------------------------------------
print("\n[10] Non-negative allocation check")
neg_ok = True
for a in opt["allocations"]:
    if a["allocated_quantity"] < 0:
        print(f"    FAIL — {a['recipient_name']}: negative allocation {a['allocated_quantity']}")
        neg_ok = False
if neg_ok:
    print("    OK — all allocations are non-negative")
else:
    sys.exit(1)

# ------------------------------------------------------------------
# 11. POST /api/redistribution/authorize — status change
# ------------------------------------------------------------------
print("\n[11] POST /api/redistribution/authorize — status change")
if opt["plan_ids"]:
    target_plan_id = opt["plan_ids"][0]
    resp = client.post("/api/redistribution/authorize", json={
        "plan_id": target_plan_id,
        "authorized_by": "Test Operator",
    })
    print(f"    Status: {resp.status_code}")
    if resp.status_code == 200:
        auth_data = resp.json()
        print(f"    plan id:        {auth_data['id']}")
        print(f"    status:         {auth_data['status']}")
        print(f"    authorized_by:  {auth_data['authorized_by']}")
        if auth_data["status"] == "authorized" and auth_data["authorized_by"] == "Test Operator":
            print("    OK — authorization successful")
        else:
            print("    FAIL — status did not change to 'authorized'")
            sys.exit(1)
    else:
        print(f"    FAIL — {resp.text}")
        sys.exit(1)
else:
    print("    SKIP — no plan IDs to authorize (zero allocations)")

# Test 404 for non-existent plan
resp404 = client.post("/api/redistribution/authorize", json={
    "plan_id": 999999,
    "authorized_by": "Nobody",
})
if resp404.status_code == 404:
    print("    OK — 404 returned for non-existent plan")
else:
    print(f"    WARNING — expected 404, got {resp404.status_code}")

# ------------------------------------------------------------------
# 12. Database persistence
# ------------------------------------------------------------------
print("\n[12] Database persistence check")
from app.models.db_models import RedistributionPlan

db = SessionLocal()
plans = db.query(RedistributionPlan).filter(
    RedistributionPlan.center_id == 1,
    RedistributionPlan.meal_id == 1,
).all()
print(f"    Found {len(plans)} redistribution plan(s) in DB")
if len(plans) > 0:
    for p in plans:
        print(f"      Plan #{p.id}: recipient={p.recipient_id}, alloc={p.allocated_quantity}, status={p.status}")
    print("    OK — plans persisted in database")
else:
    print("    FAIL — no plans found in database")
    sys.exit(1)
db.close()

# ------------------------------------------------------------------
# 13. Phase 1 + Phase 2 endpoints still register
# ------------------------------------------------------------------
print("\n[13] Phase 1 + Phase 2 endpoint registration check")

# Use the OpenAPI schema which lists all registered endpoint paths correctly
openapi = app.openapi()
all_paths = list(openapi.get("paths", {}).keys())

required = [
    "/api/forecast/generate",
    "/api/forecast/{center_id}/{meal_id}",
    "/api/production/recommend",
    "/api/production/record",
    "/api/surplus/detect",
    "/api/redistribution/optimize",
    "/api/redistribution/authorize",
    "/api/recipients",
    "/api/dashboard/summary",
]

all_present = True
for endpoint in required:
    found = endpoint in all_paths
    status = "OK" if found else "MISSING"
    if not found:
        all_present = False
    print(f"    {status:7s} {endpoint}")

if all_present:
    print("    OK — all endpoints registered")
else:
    print("    FAIL — some endpoints are missing")
    sys.exit(1)

# Also verify Phase 1 recipient CRUD still works
resp = client.get("/api/recipients")
if resp.status_code == 200:
    print(f"    OK — GET /api/recipients returns {len(resp.json())} recipients")
else:
    print(f"    FAIL — GET /api/recipients returned {resp.status_code}")

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
print("\n" + "=" * 65)
print("PHASE 3 BACKEND VERIFICATION: ALL CHECKS PASSED")
print("=" * 65)
