from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config
from .categorizer import seed_categories
from .database import Base, SessionLocal, engine
from .routers import auth, dashboard, export, transactions, uploads, budgets


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)  # swap for Alembic migrations in a larger team
    with SessionLocal() as db:
        seed_categories(db)
    yield


app = FastAPI(title="Expense Classifier API", version="1.0.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)


@app.post("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}


for r in (auth, uploads, transactions, dashboard, export, budgets):
    app.include_router(r.router)
