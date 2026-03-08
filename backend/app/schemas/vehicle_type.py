from uuid import UUID

from pydantic import BaseModel, Field


# ── Base ──────────────────────────────────────────────────────────────────────
class VehicleTypeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


# ── Create ────────────────────────────────────────────────────────────────────
class VehicleTypeCreate(VehicleTypeBase):
    pass


# ── Update ────────────────────────────────────────────────────────────────────
class VehicleTypeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)


# ── Response ──────────────────────────────────────────────────────────────────
class VehicleTypeResponse(VehicleTypeBase):
    id: UUID

    model_config = {"from_attributes": True}


class VehicleTypeList(BaseModel):
    total: int
    items: list[VehicleTypeResponse]
