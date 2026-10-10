from sqlalchemy import inspect

from app.database import engine


inspector = inspect(engine)

for column in inspector.get_columns("users"):
    print(column["name"])