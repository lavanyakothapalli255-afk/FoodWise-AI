"""FastAPI application entry point with router registration."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import (
    dashboard,
    forecast,
    production,
    recipients,
    redistribution,
    surplus,
    scenario,
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Create database tables on startup."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="SIH FoodWaste - Reduced MVP",
    description="Smart India Hackathon — Food Waste Reduction Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://food-wise-4uk3eywde-lavanya-719d.vercel.app",
        "https://food-wise-81j14j33o-lavanya-719d.vercel.app",
        "https://food-wise-ai-beta.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(forecast.router, prefix="/api/forecast", tags=["Forecast"])
app.include_router(production.router, prefix="/api/production", tags=["Production"])
app.include_router(recipients.router, prefix="/api/recipients", tags=["Recipients"])
app.include_router(
    redistribution.router, prefix="/api/redistribution", tags=["Redistribution"]
)
app.include_router(surplus.router, prefix="/api/surplus", tags=["Surplus"])
app.include_router(scenario.router, prefix="/api/scenario", tags=["Scenario"])


@app.get("/", tags=["Health"])
def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
