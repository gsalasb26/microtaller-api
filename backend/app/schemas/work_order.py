"""schemas/work_order.py — Pydantic v2 schemas for WorkOrder & WorkOrderLine.

Layout:
  WorkOrderLine   Base / Create / Response
  WorkOrder       Base / Create / Update / Response / List
  ProcessWorkOrderInput / ProcessWorkOrderResult  (atomic endpoint)
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.reception import ReceptionStatus
from app.models.work_order import WorkOrderStatus


# ── WorkOrderLine ─────────────────────────────────────────────────────────────

class WorkOrderLineBase(BaseModel):
    reception_detail_id: UUID | None = None
    description: str = Field(..., min_length=1, max_length=255)
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    unit_price: Decimal = Field(..., ge=0, decimal_places=2)
    is_part: bool = False
    discount_percentage: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=100,
        decimal_places=2,
        description="Discount as a percentage (0–100). Applied before tax.",
    )


class WorkOrderLineCreate(WorkOrderLineBase):
    pass


class WorkOrderLineResponse(WorkOrderLineBase):
    id: UUID
    work_order_id: UUID
    subtotal: Decimal

    model_config = {"from_attributes": True}


# ── WorkOrder ─────────────────────────────────────────────────────────────────

class WorkOrderBase(BaseModel):
    reception_id: UUID
    currency_id: UUID | None = None
    notes: str | None = None


class WorkOrderCreate(WorkOrderBase):
    lines: list[WorkOrderLineCreate] = []


class WorkOrderUpdate(BaseModel):
    """Mutable fields — use POST /work-orders/{id}/status for lifecycle changes."""

    currency_id: UUID | None = None
    notes: str | None = None
    status: WorkOrderStatus | None = None


class WorkOrderResponse(WorkOrderBase):
    id: UUID
    order_number: str
    status: WorkOrderStatus
    total_labor: Decimal
    total_parts: Decimal
    tax_amount: Decimal
    total_final: Decimal
    created_at: datetime
    updated_at: datetime
    lines: list[WorkOrderLineResponse] = []

    model_config = {"from_attributes": True}


class WorkOrderList(BaseModel):
    total: int
    items: list[WorkOrderResponse]


# ── Atomic process endpoint ───────────────────────────────────────────────────

class LaborItemCreate(BaseModel):
    """Pricing information for a single labour line linked to a ReceptionDetail.

    The line description is taken from the ReceptionDetail record;
    only pricing fields are supplied here.
    """

    reception_detail_id: UUID
    quantity: Decimal = Field(default=Decimal("1.000"), gt=0, decimal_places=3)
    unit_price: Decimal = Field(..., ge=0, decimal_places=2)
    discount_percentage: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=100,
        decimal_places=2,
        description="Discount as a percentage (0–100).",
    )


class ProcessWorkOrderInput(BaseModel):
    """Input for POST /work-orders/process.

    *labor_items* — one entry per ReceptionDetail to invoice; the description
    is pulled from the linked ReceptionDetail automatically.

    *extra_lines*  — additional lines (spare parts, fees) with full pricing;
    these are NOT required to reference a ReceptionDetail.
    """

    reception_id: UUID
    labor_items: list[LaborItemCreate] = Field(
        default_factory=list,
        description="Labour lines linked to ReceptionDetail rows.",
    )
    extra_lines: list[WorkOrderLineCreate] = Field(
        default_factory=list,
        description="Extra lines (parts, fees) not linked to a ReceptionDetail.",
    )
    currency_id: UUID | None = None
    notes: str | None = None
    tax_rate: Decimal = Field(
        default=Decimal("0.13"),
        ge=0,
        le=1,
        description="Tax rate expressed as a fraction, e.g. 0.13 for 13 %.",
    )


class ProcessWorkOrderResult(BaseModel):
    work_order_id: UUID
    order_number: str
    lines_created: int
    total_labor: Decimal
    total_parts: Decimal
    tax_amount: Decimal
    total_final: Decimal
    reception_status: ReceptionStatus

