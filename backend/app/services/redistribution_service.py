"""Redistribution service — Phase 3 lexicographic LP optimizer.

Adapts the Experiment 3 methodology for the service layer:
    Stage 1: Maximize total allocated meals.
    Stage 2: Minimize transport distance (fixing Stage 1 optimum).
    Stage 3: Prefer higher-priority recipients (fixing Stages 1 & 2 optima).

This is an OPERATIONAL-FEASIBILITY optimization, not a food-safety
optimization.  Hard constraints enforced:
    - allocation >= 0               (non-negativity)
    - allocation <= capacity        (recipient capacity)
    - sum(allocation) <= surplus    (total surplus)
    - allocation = 0 if unavailable (availability)
    - allocation = 0 if transit_time > usable_time  (time feasibility)

Final authorization of any redistribution plan must remain with a
human/authorized operator via POST /api/redistribution/authorize.
"""

import logging
from datetime import date

import numpy as np
from scipy.optimize import linprog
from sqlalchemy.orm import Session

from app.models.db_models import Recipient, RedistributionPlan

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------
# Feasibility helpers (adapted from Experiment 3, Section 2)
# -----------------------------------------------------------------------


def _get_feasibility_mask(
    available: np.ndarray,
    transit_times: np.ndarray,
    usable_times: np.ndarray,
) -> np.ndarray:
    """Return a boolean array: True where a recipient is feasible.

    A recipient is feasible if and only if:
        1. available == True
        2. transit_time_min <= usable_time_remaining_min
    """
    time_ok = transit_times <= usable_times
    return available & time_ok


# -----------------------------------------------------------------------
# 3-Stage lexicographic LP (adapted from Experiment 3, Section 4)
# -----------------------------------------------------------------------


def _optimizer_allocate(
    surplus: int,
    capacities: np.ndarray,
    distances: np.ndarray,
    priorities: np.ndarray,
    feasible: np.ndarray,
) -> tuple[np.ndarray, float, float, str]:
    """Genuine lexicographic optimization via 3 sequential linprog calls.

    Decision hierarchy (structurally guaranteed, not weight-based):
        Stage 1: MAXIMIZE total allocated meals.
        Stage 2: MINIMIZE transport distance (fixing Stage 1 optimum).
        Stage 3: PREFER higher-priority recipients
                 (fixing Stage 1 and Stage 2 optima).

    Adapted from Experiment 3 optimizer_allocate (frozen research code).
    Uses SciPy HiGHS solver.

    Returns
    -------
    allocation : np.ndarray  — meals allocated per recipient.
    z1_star    : float       — Stage 1 optimum (total meals allocated).
    z2_star    : float       — Stage 2 optimum (transport distance).
    status     : str         — "success" or error description.
    """
    n = len(capacities)

    # --- Variable bounds (shared across all stages) ---
    bounds = []
    for i in range(n):
        if feasible[i]:
            bounds.append((0.0, float(capacities[i])))
        else:
            bounds.append((0.0, 0.0))

    # Shared inequality: sum(x) <= surplus
    A_ub = np.ones((1, n))
    b_ub = np.array([float(surplus)])

    # ---- Stage 1: Maximize total allocated meals ----
    c1 = -np.ones(n)

    result1 = linprog(c1, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
    if not result1.success:
        logger.warning("Stage 1 failed: %s", result1.message)
        return np.zeros(n), 0.0, 0.0, f"stage1_failed: {result1.message}"

    z1_star = -result1.fun
    stage1_x = result1.x.copy()
    logger.info("Stage 1 result (max allocation): %.2f meals", z1_star)

    # ---- Stage 2: Minimize transport distance ----
    c2 = distances.copy()
    A_eq2 = np.ones((1, n))
    b_eq2 = np.array([z1_star])

    result2 = linprog(
        c2,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=A_eq2,
        b_eq=b_eq2,
        bounds=bounds,
        method="highs",
    )

    if not result2.success:
        logger.warning("Stage 2 failed: %s — falling back to Stage 1", result2.message)
        z2_star = float((stage1_x * distances).sum())
        stage2_x = stage1_x
    else:
        z2_star = result2.fun
        stage2_x = result2.x.copy()

    logger.info("Stage 2 result (min distance): %.2f meal-km", z2_star)

    # ---- Stage 3: Prefer higher-priority recipients ----
    c3 = priorities.astype(float).copy()
    A_eq3 = np.vstack([np.ones(n), distances])
    b_eq3 = np.array([z1_star, z2_star])

    result3 = linprog(
        c3,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=A_eq3,
        b_eq=b_eq3,
        bounds=bounds,
        method="highs",
    )

    if not result3.success:
        logger.warning("Stage 3 failed: %s — falling back to Stage 2", result3.message)
        allocation = stage2_x
    else:
        allocation = result3.x.copy()

    # Clip negligible floating-point noise to zero
    allocation = np.where(np.abs(allocation) < 1e-9, 0.0, allocation)

    return allocation, z1_star, z2_star, "success"


# -----------------------------------------------------------------------
# Independent constraint verification (adapted from Experiment 3, Section 5)
# -----------------------------------------------------------------------


def _verify_constraints(
    allocation: np.ndarray,
    surplus: int,
    capacities: np.ndarray,
    available: np.ndarray,
    transit_times: np.ndarray,
    usable_times: np.ndarray,
) -> tuple[int, list[str]]:
    """Independent post-solve verification of every hard constraint.

    Checks:
        1. x[i] >= 0               (non-negativity)
        2. x[i] <= capacity_i      (capacity)
        3. sum(x[i]) <= surplus     (total surplus)
        4. x[i] == 0 if unavailable (availability)
        5. x[i] == 0 if transit > usable (time feasibility)

    Returns (violation_count, violation_details).
    """
    TOL = 1e-9
    violations = 0
    details: list[str] = []

    for i in range(len(allocation)):
        # 1. Non-negativity
        if allocation[i] < -TOL:
            violations += 1
            details.append(f"Recipient idx {i}: negative allocation ({allocation[i]:.6f})")

        # 2. Capacity
        if allocation[i] > capacities[i] + TOL:
            violations += 1
            details.append(
                f"Recipient idx {i}: exceeds capacity "
                f"({allocation[i]:.2f} > {capacities[i]})"
            )

        # 3. Availability
        if not available[i] and allocation[i] > TOL:
            violations += 1
            details.append(
                f"Recipient idx {i}: allocated {allocation[i]:.2f} "
                f"to unavailable recipient"
            )

        # 4. Time feasibility
        if transit_times[i] > usable_times[i] and allocation[i] > TOL:
            violations += 1
            details.append(
                f"Recipient idx {i}: allocated {allocation[i]:.2f} "
                f"to time-infeasible recipient "
                f"(transit={transit_times[i]}min > usable={usable_times[i]}min)"
            )

    # 5. Total surplus
    total = float(allocation.sum())
    if total > surplus + TOL:
        violations += 1
        details.append(f"Total allocation ({total:.2f}) exceeds surplus ({surplus})")

    return violations, details


class RedistributionService:
    """Handles redistribution optimization and authorization."""

    def optimize(
        self,
        center_id: int,
        meal_id: int,
        target_date: date,
        surplus_qty: int,
        recipient_overrides: list[dict],
        db: Session,
        persist: bool = True,
    ) -> dict:
        """Optimize redistribution of surplus to recipients.

        Uses 3-stage lexicographic LP adapted from Experiment 3.

        Parameters
        ----------
        center_id : int
        meal_id : int
        target_date : date
        surplus_qty : int
            Number of surplus meals to redistribute.
        recipient_overrides : list[dict]
            Per-recipient operational data.  Each dict must have:
            recipient_id, distance_km, transit_time_min,
            usable_time_remaining_min, priority.
        db : Session

        Returns
        -------
        dict
            Full optimization result with allocations, metrics, and plan IDs.
        """

        # --- 1. Build the override lookup ---
        override_map: dict[int, dict] = {}
        for entry in recipient_overrides:
            override_map[entry["recipient_id"]] = entry

        # --- 2. Fetch active recipients from DB (only those in overrides) ---
        recipient_ids = list(override_map.keys())
        recipients = (
            db.query(Recipient)
            .filter(Recipient.id.in_(recipient_ids))
            .all()
        )

        if not recipients:
            return {
                "center_id": center_id,
                "meal_id": meal_id,
                "date": target_date,
                "surplus_quantity": surplus_qty,
                "total_allocated": 0,
                "unallocated_surplus": surplus_qty,
                "total_transport_distance": 0.0,
                "allocation_percentage": 0.0,
                "solver_status": "no_eligible_recipients",
                "constraint_violations": 0,
                "allocations": [],
                "plan_ids": [],
                "authorization_status": "no_plan",
            }

        # --- 3. Build arrays for the optimizer ---
        n = len(recipients)
        capacities = np.zeros(n)
        distances = np.zeros(n)
        transit_times = np.zeros(n)
        usable_times = np.zeros(n)
        priorities = np.zeros(n)
        available = np.zeros(n, dtype=bool)

        for i, r in enumerate(recipients):
            ov = override_map[r.id]
            capacities[i] = float(r.capacity)
            distances[i] = float(ov["distance_km"])
            transit_times[i] = float(ov["transit_time_min"])
            usable_times[i] = float(ov["usable_time_remaining_min"])
            priorities[i] = float(ov["priority"])
            available[i] = r.is_active

        # --- 4. Feasibility mask ---
        feasible = _get_feasibility_mask(available, transit_times, usable_times)

        # --- 5. Run optimizer ---
        allocation, z1_star, z2_star, solver_status = _optimizer_allocate(
            surplus_qty, capacities, distances, priorities, feasible
        )

        # --- 6. Independent constraint verification ---
        violations, violation_details = _verify_constraints(
            allocation, surplus_qty, capacities, available, transit_times, usable_times
        )
        if violations > 0:
            for detail in violation_details:
                logger.warning("Constraint violation: %s", detail)

        # --- 7. Compute metrics ---
        total_allocated = int(round(float(allocation.sum())))
        unallocated = surplus_qty - total_allocated
        total_distance = float((allocation * distances).sum())
        alloc_pct = (
            round(total_allocated / surplus_qty * 100, 2) if surplus_qty > 0 else 0.0
        )

        # --- 8. Persist redistribution plans and build response ---
        allocations_out: list[dict] = []
        plan_ids: list[int] = []

        for i, r in enumerate(recipients):
            ov = override_map[r.id]
            alloc_qty = int(round(float(allocation[i])))
            is_feas = bool(feasible[i])
            is_time_feas = bool(transit_times[i] <= usable_times[i])

            # Persist only non-zero allocations
            if alloc_qty > 0:
                if persist:
                    plan = RedistributionPlan(
                        center_id=center_id,
                        meal_id=meal_id,
                        recipient_id=r.id,
                        date=target_date,
                        surplus_quantity=surplus_qty,
                        allocated_quantity=alloc_qty,
                        status="recommended",
                    )
                    db.add(plan)
                    db.flush()  # get the ID without committing yet
                    plan_ids.append(plan.id)

            allocations_out.append(
                {
                    "recipient_id": r.id,
                    "recipient_name": r.name,
                    "capacity": r.capacity,
                    "is_available": r.is_active,
                    "is_time_feasible": is_time_feas,
                    "distance_km": ov["distance_km"],
                    "transit_time_min": ov["transit_time_min"],
                    "usable_time_remaining_min": ov["usable_time_remaining_min"],
                    "priority": ov["priority"],
                    "allocated_quantity": alloc_qty,
                    "is_feasible": is_feas,
                }
            )

        if persist:
            db.commit()

        return {
            "center_id": center_id,
            "meal_id": meal_id,
            "date": target_date,
            "surplus_quantity": surplus_qty,
            "total_allocated": total_allocated,
            "unallocated_surplus": unallocated,
            "total_transport_distance": round(total_distance, 2),
            "allocation_percentage": alloc_pct,
            "solver_status": solver_status,
            "constraint_violations": violations,
            "allocations": allocations_out,
            "plan_ids": plan_ids,
            "authorization_status": "pending_authorization",
        }

    def authorize(
        self,
        plan_id: int,
        authorized_by: str,
        db: Session,
    ) -> RedistributionPlan | None:
        """Authorize a redistribution plan.

        Changes the plan's status from 'recommended' to 'authorized'
        and records who authorized it.

        Returns None if the plan is not found.
        """
        plan = (
            db.query(RedistributionPlan)
            .filter(RedistributionPlan.id == plan_id)
            .first()
        )
        if plan is None:
            return None

        plan.status = "authorized"
        plan.authorized_by = authorized_by
        db.commit()
        db.refresh(plan)
        return plan


# Module-level singleton
redistribution_service = RedistributionService()
