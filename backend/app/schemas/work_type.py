from uuid import UUID

from pydantic import BaseModel, Field


# ── Base ──────────────────────────────────────────────────────────────────────
class WorkTypeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str | None = Field(None, max_length=500)


# ── Create ────────────────────────────────────────────────────────────────────
class WorkTypeCreate(WorkTypeBase):
    pass


# ── Update ────────────────────────────────────────────────────────────────────
class WorkTypeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=500)


# ── Response ──────────────────────────────────────────────────────────────────
class WorkTypeResponse(WorkTypeBase):
    id: UUID

    model_config = {"from_attributes": True}


class WorkTypeList(BaseModel):
    total: int
    items: list[WorkTypeResponse]
