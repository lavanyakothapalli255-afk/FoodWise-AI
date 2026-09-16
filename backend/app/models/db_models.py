"""SQLAlchemy ORM models for the 7 approved tables."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Center(Base):
    """Food production center."""

    __tablename__ = "centers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str] = mapped_column(String(300), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    historical_demands = relationship("HistoricalDemand", back_populates="center")
    forecasts = relationship("Forecast", back_populates="center")
    production_decisions = relationship("ProductionDecision", back_populates="center")
    redistribution_plans = relationship("RedistributionPlan", back_populates="center")


class Meal(Base):
    """Meal type served by centers."""

    __tablename__ = "meals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    shelf_life_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    historical_demands = relationship("HistoricalDemand", back_populates="meal")
    forecasts = relationship("Forecast", back_populates="meal")
    production_decisions = relationship("ProductionDecision", back_populates="meal")
    redistribution_plans = relationship("RedistributionPlan", back_populates="meal")


class Recipient(Base):
    """Surplus food recipient (NGO, shelter, food bank, etc.)."""

    __tablename__ = "recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(300), nullable=False)
    contact_info: Mapped[str] = mapped_column(String(300), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    redistribution_plans = relationship(
        "RedistributionPlan", back_populates="recipient"
    )


class HistoricalDemand(Base):
    """Historical meal demand and waste data."""

    __tablename__ = "historical_demand"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    center_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("centers.id"), nullable=False
    )
    meal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("meals.id"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity_demanded: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_produced: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_wasted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    center = relationship("Center", back_populates="historical_demands")
    meal = relationship("Meal", back_populates="historical_demands")


class Forecast(Base):
    """Demand forecast for a center-meal combination."""

    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    center_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("centers.id"), nullable=False
    )
    meal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("meals.id"), nullable=False
    )
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    predicted_demand: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_lower: Mapped[float] = mapped_column(Float, nullable=True)
    confidence_upper: Mapped[float] = mapped_column(Float, nullable=True)
    model_version: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    center = relationship("Center", back_populates="forecasts")
    meal = relationship("Meal", back_populates="forecasts")


class ProductionDecision(Base):
    """Production quantity decision for a center-meal-date."""

    __tablename__ = "production_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    center_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("centers.id"), nullable=False
    )
    meal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("meals.id"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    recommended_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_quantity: Mapped[int] = mapped_column(Integer, nullable=True)
    decision_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    center = relationship("Center", back_populates="production_decisions")
    meal = relationship("Meal", back_populates="production_decisions")


class RedistributionPlan(Base):
    """Plan for redistributing surplus food to recipients."""

    __tablename__ = "redistribution_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    center_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("centers.id"), nullable=False
    )
    meal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("meals.id"), nullable=False
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipients.id"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    surplus_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )
    authorized_by: Mapped[str] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    center = relationship("Center", back_populates="redistribution_plans")
    meal = relationship("Meal", back_populates="redistribution_plans")
    recipient = relationship("Recipient", back_populates="redistribution_plans")
