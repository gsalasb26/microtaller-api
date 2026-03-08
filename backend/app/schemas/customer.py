from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ── Base ──────────────────────────────────────────────────────────────────────
class CustomerBase(BaseModel):
    name: str = Field(..., max_length=100)
    phone: str = Field(..., max_length=20)
    email: EmailStr | None = None
    notes: str | None = None


# ── Create ────────────────────────────────────────────────────────────────────
class CustomerCreate(CustomerBase):
    pass


# ── Update ────────────────────────────────────────────────────────────────────
class CustomerUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    email: EmailStr | None = None
    notes: str | None = None


# ── Response ──────────────────────────────────────────────────────────────────
class CustomerResponse(CustomerBase):
    id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerList(BaseModel):
    total: int
    items: list[CustomerResponse]
