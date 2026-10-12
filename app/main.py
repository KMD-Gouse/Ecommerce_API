
from fastapi import FastAPI

from app.routers import orders, products, users,auth


app = FastAPI(title="Mini E-Commerce API")
app.include_router(auth.router)


app.include_router(users.router)
app.include_router(products.router)
app.include_router(orders.router)


@app.get("/")
def home():
    return {"message": "E-Commerce API"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/about")
def about():
    return {
        "project": "Mini E-Commerce API",
        
    }