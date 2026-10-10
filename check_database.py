from sqlalchemy import text

from app.database import SessionLocal


with SessionLocal() as db:
    result = db.execute(text("SELECT 1")).scalar_one()

    print("Database connection successful!")
    print("Result:", result)