from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.vehicle_type import VehicleTypeResponse


# ── Base ──────────────────────────────────────────────────────────────────────
class VehicleBase(BaseModel):
    customer_id: UUID
    vehicle_type_id: UUID | None = None
    brand: str = Field(..., max_length=80)
    model: str = Field(..., max_length=80)
    year: int = Field(..., ge=1900, le=2100)
    plate: str = Field(..., max_length=20)


# ── Create ────────────────────────────────────────────────────────────────────
class VehicleCreate(VehicleBase):
    pass


# ── Update ────────────────────────────────────────────────────────────────────
class VehicleUpdate(BaseModel):
    vehicle_type_id: UUID | None = None
    brand: str | None = Field(None, max_length=80)
    model: str | None = Field(None, max_length=80)
    year: int | None = Field(None, ge=1900, le=2100)
    plate: str | None = Field(None, max_length=20)


# ── Response ──────────────────────────────────────────────────────────────────
class VehicleResponse(VehicleBase):
    id: UUID
    created_at: datetime
    vehicle_type: VehicleTypeResponse | None = None

    model_config = {"from_attributes": True}


class VehicleList(BaseModel):
    total: int
    items: list[VehicleResponse]
