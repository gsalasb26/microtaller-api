from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.routers import (
    currencies_router,
    customers_router,
    reception_details_router,
    receptions_router,
    vehicle_types_router,
    vehicles_router,
    work_orders_router,
    work_types_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify database connection
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    print(
        f"[OK] Database connection established -- "
        f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )

    if settings.SEED_ON_STARTUP:
        print("[INFO] SEED_ON_STARTUP=true — running seed data...")
        from app.seed_data import run_seed
        await run_seed()

    yield
    # Shutdown: close connection pool
    await engine.dispose()
    print("[OK] Database connections closed")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Work order management system for small auto repair shops. "
        "Manages customers, vehicles, and work orders with their line items."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# -- CORS ---------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Routers ------------------------------------------------------------------
app.include_router(currencies_router, prefix="/api/v1")
app.include_router(customers_router, prefix="/api/v1")
app.include_router(reception_details_router, prefix="/api/v1")
app.include_router(receptions_router, prefix="/api/v1")
app.include_router(vehicle_types_router, prefix="/api/v1")
app.include_router(vehicles_router, prefix="/api/v1")
app.include_router(work_orders_router, prefix="/api/v1")
app.include_router(work_types_router, prefix="/api/v1")


# -- Health check -------------------------------------------------------------
@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# -- Seed (only available when DEBUG=true) ------------------------------------
if settings.DEBUG:
    @app.post("/seed", tags=["Dev"], summary="Populate DB with initial seed data")
    async def seed():
        """Idempotent: inserts currencies, vehicle types, customers and vehicles
        only if they don't already exist. Only exposed when DEBUG=true."""
        from app.seed_data import run_seed
        await run_seed()
        return {"status": "ok", "message": "Seed completed"}  