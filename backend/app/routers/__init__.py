from app.routers.currencies import router as currencies_router
from app.routers.customers import router as customers_router
from app.routers.vehicle_types import router as vehicle_types_router
from app.routers.vehicles import router as vehicles_router
from app.routers.work_orders import router as work_orders_router

__all__ = ["currencies_router", "customers_router", "vehicle_types_router", "vehicles_router", "work_orders_router"]
