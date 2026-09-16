"""Seed script to populate reference data (centers and meals)."""

from app.database import SessionLocal, engine, Base
from app.models.db_models import Center, Meal, Recipient


def seed():
    """Insert initial center and meal reference data."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Only seed if tables are empty
        if db.query(Center).count() == 0:
            centers = [
                Center(name="Central Kitchen A", location="Delhi", capacity=5000),
                Center(name="Central Kitchen B", location="Mumbai", capacity=4000),
                Center(name="Central Kitchen C", location="Chennai", capacity=3500),
            ]
            db.add_all(centers)
            db.commit()
            print(f"Seeded {len(centers)} centers.")
        else:
            print("Centers already seeded — skipping.")

        if db.query(Meal).count() == 0:
            meals = [
                Meal(name="Breakfast", category="morning", shelf_life_hours=4),
                Meal(name="Lunch", category="afternoon", shelf_life_hours=3),
                Meal(name="Dinner", category="evening", shelf_life_hours=3),
                Meal(name="Snack", category="anytime", shelf_life_hours=6),
            ]
            db.add_all(meals)
            db.commit()
            print(f"Seeded {len(meals)} meals.")
        else:
            print("Meals already seeded — skipping.")

        if db.query(Recipient).count() == 0:
            recipients = [
                Recipient(name="City Shelter A", type="shelter", location="Area 1", capacity=2000, is_active=True),
                Recipient(name="Food Bank B", type="food_bank", location="Area 2", capacity=1500, is_active=True),
                Recipient(name="Community Kitchen C", type="community", location="Area 3", capacity=1000, is_active=True),
                Recipient(name="Unavailable Center D", type="ngo", location="Area 4", capacity=500, is_active=False),
            ]
            db.add_all(recipients)
            db.commit()
            print(f"Seeded {len(recipients)} recipients.")
        else:
            print("Recipients already seeded — skipping.")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
