from sqlalchemy import inspect
from sqlalchemy.orm import configure_mappers

from app.database import Base, engine
from app.models.users import User
from app.models.products import Product
from app.models.orders import Order


configure_mappers()

Base.metadata.create_all(bind=engine)

inspector = inspect(engine)

print("Tables:", inspector.get_table_names())

for column in inspector.get_columns("orders"):
    print("Order column:", column["name"])