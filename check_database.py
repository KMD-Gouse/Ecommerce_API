from sqlalchemy import text

from app.database import engine


with engine.connect() as connection:
    database_name = connection.execute(
        text("SELECT current_database()")
    ).scalar_one()

    database_user = connection.execute(
        text("SELECT current_user")
    ).scalar_one()

    print("Database connection successful!")
    print("Database:", database_name)
    print("User:", database_user)