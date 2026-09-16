"""Pydantic schemas for API request/response validation."""

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Recipient schemas (full CRUD for Phase 1)
# ---------------------------------------------------------------------------


class RecipientCreate(BaseModel):
    """Schema for creating a new recipient."""

    name: str
    type: str
    location: str
    contact_info: Optional[str] = None
    capacity: int
    is_active: bool = True


class RecipientUpdate(BaseModel):
    """Schema for updating an existing recipient."""

    name: Optional[str] = None
    type: Optional[str] = None
    location: Optional[str] = None
    contact_info: Optional[str] = None
    capacity: Optional[int] = None
    is_active: Optional[bool] = None


class RecipientRead(BaseModel):
    """Schema for reading a recipient."""

    id: int
    name: str
    type: str
    location: str
    contact_info: Optional[str]
    capacity: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Center schemas (read-only reference data)
# ---------------------------------------------------------------------------


class CenterRead(BaseModel):
    """Schema for reading a center."""

    id: int
    name: str
    location: str
    capacity: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Meal schemas (read-only reference data)
# ---------------------------------------------------------------------------


class MealRead(BaseModel):
    """Schema for reading a meal."""

    id: int
    name: str
    category: str
    shelf_life_hours: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Forecast schemas (stubs for later phases)
# ---------------------------------------------------------------------------


class HistoricalObservation(BaseModel):
    """Schema for a historical demand observation."""

    week: int
    num_orders: int


class ForecastRequest(BaseModel):
    """Schema for requesting a forecast generation."""

    center_id: int
    meal_id: int
    target_date: date


class ForecastRead(BaseModel):
    """Schema for reading a forecast."""

    id: int
    center_id: int
    meal_id: int
    forecast_date: date
    predicted_demand: float
    confidence_lower: Optional[float]
    confidence_upper: Optional[float]
    model_version: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Production schemas (stubs for later phases)
# ---------------------------------------------------------------------------


class ProductionRecommendRequest(BaseModel):
    """Schema for requesting a production recommendation.

    The policy parameter selects the service-level/waste trade-off:
      - p50: point forecast (lowest surplus, highest shortage risk)
      - p70: moderate buffer
      - p80: prototype default (balanced, not universally optimal)
      - p90: conservative buffer
      - p95: aggressive buffer (lowest shortage risk, highest surplus)
      - historical_mean: baseline using training-period average

    Each policy represents a different trade-off, not a universal optimum.
    """

    center_id: int
    meal_id: int
    date: date
    policy: Literal["p50", "p70", "p80", "p90", "p95", "historical_mean"] = "p80"


class ProductionRecordRequest(BaseModel):
    """Schema for recording actual production."""

    center_id: int
    meal_id: int
    date: date
    actual_quantity: int


class ProductionDecisionRead(BaseModel):
    """Schema for reading a production decision."""

    id: int
    center_id: int
    meal_id: int
    date: date
    recommended_quantity: int
    actual_quantity: Optional[int]
    decision_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductionRecommendResponse(BaseModel):
    """Response for production recommendation, including trade-off transparency.

    Includes the DB-persisted decision fields plus computed fields
    (policy_used, point_forecast, expected_surplus, expected_shortage)
    that make the service-level/waste trade-off explicit.
    """

    id: int
    center_id: int
    meal_id: int
    date: date
    recommended_quantity: int
    actual_quantity: Optional[int]
    decision_status: str
    created_at: datetime
    policy_used: str
    point_forecast: float
    expected_surplus: float
    expected_shortage: float


# ---------------------------------------------------------------------------
# Surplus schemas (Phase 3)
# ---------------------------------------------------------------------------


class SurplusDetectRequest(BaseModel):
    """Schema for requesting surplus detection.

    If actual_consumption is not provided, the service uses the
    forecasted demand as a proxy for consumption (prototype behaviour).
    """

    center_id: int
    meal_id: int
    date: date
    actual_consumption: Optional[int] = None


class SurplusDetectResponse(BaseModel):
    """Response for surplus detection.

    Statuses:
      - no_data: no recorded production found for this center-meal-date
      - no_surplus: actual production <= consumption; surplus is zero
      - surplus_detected: surplus is available for redistribution evaluation

    The eligibility_advisory is an informational flag based on meal
    shelf-life.  It does NOT constitute a food-safety guarantee.
    Final food-safety authorization must remain with a human/authorized
    operator.
    """

    center_id: int
    meal_id: int
    date: date
    actual_production: int
    actual_consumption: int
    surplus_quantity: int
    shortage_quantity: int
    status: str
    eligibility_advisory: str
    usable_time_remaining_min: Optional[float] = None


# ---------------------------------------------------------------------------
# Redistribution schemas (Phase 3)
# ---------------------------------------------------------------------------


class RecipientOperationalData(BaseModel):
    """Per-recipient operational parameters provided at optimization time.

    These values are inherently dynamic — distance depends on the
    originating center, usable time depends on preparation time, and
    priority may change based on operational context.

    They are NOT stored in the recipients DB table because they are
    event-specific, not static recipient attributes.
    """

    recipient_id: int
    distance_km: float = Field(..., ge=0.0, description="Distance in km (>= 0)")
    transit_time_min: float = Field(
        ..., ge=0.0, description="Transit time in minutes (>= 0)"
    )
    usable_time_remaining_min: float = Field(
        ..., ge=0.0, description="Usable time remaining in minutes (>= 0)"
    )
    priority: int = Field(
        ..., ge=1, description="Priority level (1 = highest priority, >= 1)"
    )


class RedistributionOptimizeRequest(BaseModel):
    """Schema for requesting redistribution optimization.

    The recipient_overrides list provides per-recipient operational
    data (distance, transit time, usable time, priority) that the
    optimizer needs.  Each entry must reference an existing recipient
    by ID.  Recipients not included are treated as unavailable for
    this optimization run.
    """

    center_id: int
    meal_id: int
    date: date
    surplus_quantity: int = Field(..., gt=0, description="Surplus meals (> 0)")
    recipient_overrides: List[RecipientOperationalData]


class RecipientAllocation(BaseModel):
    """Per-recipient allocation in the optimization result."""

    recipient_id: int
    recipient_name: str
    capacity: int
    is_available: bool
    is_time_feasible: bool
    distance_km: float
    transit_time_min: float
    usable_time_remaining_min: float
    priority: int
    allocated_quantity: int
    is_feasible: bool


class RedistributionOptimizeResponse(BaseModel):
    """Full optimization result.

    This is an operational-feasibility optimization, NOT a food-safety
    optimization.  The optimizer enforces capacity, availability,
    time-feasibility, and non-negativity constraints.

    The plan_ids reference the persisted RedistributionPlan rows
    (status='recommended') that require human authorization via
    POST /api/redistribution/authorize before becoming final.
    """

    center_id: int
    meal_id: int
    date: date
    surplus_quantity: int
    total_allocated: int
    unallocated_surplus: int
    total_transport_distance: float
    allocation_percentage: float
    solver_status: str
    constraint_violations: int
    allocations: List[RecipientAllocation]
    plan_ids: List[int]
    authorization_status: str


class RedistributionAuthorizeRequest(BaseModel):
    """Schema for authorizing a redistribution plan."""

    plan_id: int
    authorized_by: str


class RedistributionPlanRead(BaseModel):
    """Schema for reading a redistribution plan."""

    id: int
    center_id: int
    meal_id: int
    recipient_id: int
    date: date
    surplus_quantity: int
    allocated_quantity: int
    status: str
    authorized_by: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Dashboard schemas (stub for later phases)
# ---------------------------------------------------------------------------


class DashboardSummary(BaseModel):
    """Schema for dashboard summary response using only actual DB data."""

    total_centers: int = 0
    total_meals: int = 0
    total_recipients: int = 0
    total_forecasts: int = 0
    total_production_decisions: int = 0
    total_redistribution_plans: int = 0
    authorized_plans: int = 0
