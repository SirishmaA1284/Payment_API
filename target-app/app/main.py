from fastapi import FastAPI

from app.auth import router as auth_router
from app.database import init_db

app = FastAPI(title="Payment API")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def health_check() -> dict:
    return {"status": "ok", "service": "payment-api"}


app.include_router(auth_router)
