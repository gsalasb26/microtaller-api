from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from app.models.work_order import OrderStatus


# ── Work Order Item ───────────────────────────────────────────────────────────

class WorkOrderItemBase(BaseModel):
    description: str = Field(..., min_length=1, max_length=255)
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    unit_price: Decimal = Field(..., ge=0, decimal_places=2)
    currency_id: UUID | None = None


class WorkOrderItemCreate(WorkOrderItemBase):
    pass


class WorkOrderItemUpdate(BaseModel):
    description: str | None = Field(None, min_length=1, max_length=255)
    quantity: Decimal | None = Field(None, gt=0, decimal_places=3)
    unit_price: Decimal | None = Field(None, ge=0, decimal_places=2)
    currency_id: UUID | None = None


class WorkOrderItemResponse(WorkOrderItemBase):
    id: UUID
    work_order_id: UUID
    total: Decimal

    model_config = {"from_attributes": True}


# ── Work Order ────────────────────────────────────────────────────────────────

class WorkOrderBase(BaseModel):
    vehicle_id: UUID
    checkin_photos: list[str] | None = None
    notes: str | None = None


class WorkOrderCreate(WorkOrderBase):
    items: list[WorkOrderItemCreate] = []


class WorkOrderUpdate(BaseModel):
    """Fields the caller may change via PATCH.

    Status changes are intentionally restricted to keep the state machine
    enforced: use POST /{id}/close to deliver a work order.
    Allowed only: received -> in_progress.
    """

    status: OrderStatus | None = None
    checkin_photos: list[str] | None = None
    notes: str | None = None


class WorkOrderResponse(WorkOrderBase):
    id: UUID
    status: OrderStatus
    created_at: datetime
    closed_at: datetime | None
    items: list[WorkOrderItemResponse] = []

    @computed_field  # type: ignore[misc]
    @property
    def total(self) -> Decimal:
        """Grand total computed from items — never stored on the work order."""
        return sum((i.total for i in self.items), Decimal("0.00"))

    model_config = {"from_attributes": True}


class WorkOrderList(BaseModel):
    total: int
    items: list[WorkOrderResponse]

