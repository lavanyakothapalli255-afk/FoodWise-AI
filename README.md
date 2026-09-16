# FoodWise AI

## AI-Powered Smart Food Waste Reduction and Sustainable Redistribution Ecosystem

FoodWise AI is an AI-powered decision-support system designed for institutional kitchens to reduce avoidable food waste by improving demand prediction, production planning, and surplus redistribution.

## Problem

Institutional kitchens must prepare food before knowing the exact demand.

This uncertainty can lead to:

**Uncertain Demand -> Overproduction -> Surplus -> Quality Deterioration -> Food Waste**

FoodWise AI follows a **Prevent First, Rescue Second** approach.

## Our Approach

The system connects demand forecasting with production decisions and surplus response.

**Historical Demand**
↓
**AI Demand Forecast**
↓
**Production Recommendation**
↓
**Actual Production & Consumption**
↓
**Surplus / Shortage Detection**
↓
**Constraint-Aware Redistribution**
↓
**Human Authorization**
↓
**Outcome Feedback**

## Key Features

- AI-based institutional meal demand forecasting
- Risk-aware production recommendations
- P50-P95 production policy options
- Surplus and shortage detection
- Recipient capacity and availability checks
- Distance and time feasibility checks
- Constraint-aware redistribution planning
- Human-in-the-loop authorization
- Decision and activity dashboard

## Prototype Experiments

### Demand Forecasting

Our machine-learning forecasting experiment achieved approximately **16.9% lower MAE** than a historical-mean baseline on our held-out evaluation period.

> This measures improvement in **forecast accuracy**, not a 16.9% reduction in food waste.

### Production Decision Policies

The prototype evaluates multiple production policies from **P50 to P95**, demonstrating the trade-off between shortage risk and potential surplus.

### Redistribution Optimization

The redistribution experiment evaluates recipient capacity, availability, distance, and time feasibility.

Across the tested synthetic scenarios:

- 15 optimization runs
- 5 scenarios
- 0 hard-constraint violations

## Technology Stack

### Backend

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL

### AI / Data Science

- Scikit-learn
- NumPy
- Pandas
- SciPy

### Frontend

- React
- TypeScript
- Vite

## System Architecture

Historical + Operational Data
↓
Demand Forecasting
↓
Production Planning
↓
Actual Outcome
↓
Surplus Detection
↓
Quality / Operational Checks
↓
Decision Engine
↓
Prevent / Rescue
↓
Recipient Matching
↓
Route Feasibility
↓
Human Authorization

## Human-in-the-Loop

Food redistribution is not automatically authorized by the system.

The prototype generates a recommended redistribution plan, while an authorized human operator performs the final authorization.

## Current Prototype

The current software prototype demonstrates the complete workflow:

**Predict -> Decide -> Detect -> Rescue -> Authorize**

The prototype currently focuses on institutional kitchens and uses operational data for production and surplus decisions.

Future deployments can integrate additional data sources such as weighing systems, IoT sensors, or computer vision.

## Running Locally

### Backend

    cd backend
    python main.py

### Frontend

    cd frontend
    npm install
    npm run dev

Configure the required environment variables in `.env`.

## Project Structure

    FoodWise-AI/
    ├── backend/
    │   ├── app/
    │   │   ├── models/
    │   │   ├── routers/
    │   │   └── services/
    │   ├── main.py
    │   └── seed.py
    ├── data/
    ├── experiments/
    ├── frontend/
    ├── .gitignore
    └── README.md

## Vision

FoodWise AI aims to help institutions make better food production decisions, reduce avoidable surplus, and create a structured pathway for redistributing unavoidable surplus.

### Prevent First. Rescue Second.
