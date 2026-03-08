from uuid import UUID

from pydantic import BaseModel, Field


# ── Base ──────────────────────────────────────────────────────────────────────
class CurrencyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    code: str = Field(..., min_length=3, max_length=3, description="ISO-4217 code, e.g. USD")
    symbol: str = Field(..., min_length=1, max_length=5)


# ── Create ────────────────────────────────────────────────────────────────────
class CurrencyCreate(CurrencyBase):
    pass


# ── Update ────────────────────────────────────────────────────────────────────
class CurrencyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    code: str | None = Field(None, min_length=3, max_length=3)
    symbol: str | None = Field(None, min_length=1, max_length=5)


# ── Response ──────────────────────────────────────────────────────────────────
class CurrencyResponse(CurrencyBase):
    id: UUID

    model_config = {"from_attributes": True}


class CurrencyList(BaseModel):
    total: int
    items: list[CurrencyResponse]
