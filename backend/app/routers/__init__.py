from app.routers.currencies import router as currencies_router
from app.routers.customers import router as customers_router
from app.routers.reception_details import router as reception_details_router
from app.routers.receptions import router as receptions_router
from app.routers.vehicle_types import router as vehicle_types_router
from app.routers.vehicles import router as vehicles_router
from app.routers.work_orders import router as work_orders_router
from app.routers.work_types import router as work_types_router

__all__ = [
    "currencies_router",
    "customers_router",
    "reception_details_router",
    "receptions_router",
    "vehicle_types_router",
    "vehicles_router",
    "work_orders_router",
    "work_types_router",
]
