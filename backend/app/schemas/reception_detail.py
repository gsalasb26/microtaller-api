"""reception_detail.py — Schemas Pydantic para trabajos realizados en una recepción."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.work_type import WorkTypeResponse


# ── Base (used for inline initial_works inside /process) ─────────────────────
class ReceptionDetailBase(BaseModel):
    work_type_id: UUID
    description: str = Field(..., min_length=1, max_length=2000)
    work_date: datetime | None = Field(
        None,
        description="Fecha efectiva del trabajo. Si se omite, se usa el momento de creación.",
    )


# ── Create (standalone POST /reception-details — reception_id required) ───────
class ReceptionDetailCreate(ReceptionDetailBase):
    reception_id: UUID


# ── Update (solo description y work_date) ────────────────────────────────────
class ReceptionDetailUpdate(BaseModel):
    description: str | None = Field(None, min_length=1, max_length=2000)
    work_date: datetime | None = None


# ── Response ──────────────────────────────────────────────────────────────────
class ReceptionDetailResponse(BaseModel):
    id: UUID
    reception_id: UUID
    work_type_id: UUID
    description: str
    work_date: datetime
    created_at: datetime
    updated_at: datetime
    work_type: WorkTypeResponse | None = None

    model_config = {"from_attributes": True}


class ReceptionDetailList(BaseModel):
    total: int
    items: list[ReceptionDetailResponse]
