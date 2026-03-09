"""work_order.py — Presupuesto / Orden de Trabajo (cabecera + líneas de costo).

Ciclo de vida del documento:
    DRAFT → SENT → APPROVED → INVOICED
    cualquier estado → CANCELLED  (excepto INVOICED)

Relaciones con el módulo de Recepción:
    Reception  1────N  WorkOrder
    WorkOrder  1────N  WorkOrderLine
    WorkOrderLine  0..1────  ReceptionDetail  (si el costo viene de un trabajo realizado)
"""
import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# WorkOrderStatus enum
# ---------------------------------------------------------------------------

class WorkOrderStatus(str, enum.Enum):
    """Document lifecycle for a work-order / budget.

    Allowed transitions:
      DRAFT     → SENT, CANCELLED
      SENT      → APPROVED, CANCELLED
      APPROVED  → INVOICED, CANCELLED
      INVOICED  → (terminal)
      CANCELLED → (terminal)
    """

    DRAFT     = "DRAFT"
    SENT      = "SENT"
    APPROVED  = "APPROVED"
    INVOICED  = "INVOICED"
    CANCELLED = "CANCELLED"


# Allowed transitions table used by the router
WORK_ORDER_TRANSITIONS: dict[WorkOrderStatus, set[WorkOrderStatus]] = {
    WorkOrderStatus.DRAFT:     {WorkOrderStatus.SENT, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.SENT:      {WorkOrderStatus.APPROVED, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.APPROVED:  {WorkOrderStatus.INVOICED, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.INVOICED:  set(),
    WorkOrderStatus.CANCELLED: set(),
}


# ---------------------------------------------------------------------------
# WorkOrder — cabecera
# ---------------------------------------------------------------------------

class WorkOrder(Base):
    """Budget / Work-Order header linked to a Reception."""

    __tablename__ = "work_orders"
    __table_args__ = (
        Index("ix_work_orders_reception_id", "reception_id"),
        Index("ix_work_orders_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reception_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("receptions.id", name="fk_work_orders_reception_id", ondelete="RESTRICT"),
        nullable=False,
    )
    currency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("currencies.id", name="fk_work_orders_currency_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    order_number: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True, index=True
    )
    status: Mapped[WorkOrderStatus] = mapped_column(
        Enum(WorkOrderStatus, name="work_order_status"),
        nullable=False,
        default=WorkOrderStatus.DRAFT,
        server_default=WorkOrderStatus.DRAFT.value,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_labor: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0.00"
    )
    total_parts: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0.00"
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0.00"
    )
    total_final: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0.00"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    reception: Mapped["Reception"] = relationship(  # noqa: F821
        back_populates="work_orders", lazy="selectin"
    )
    currency: Mapped["Currency"] = relationship(  # noqa: F821
        back_populates="work_orders", lazy="selectin"
    )
    lines: Mapped[list["WorkOrderLine"]] = relationship(
        back_populates="work_order",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="WorkOrderLine.id",
    )


# ---------------------------------------------------------------------------
# WorkOrderLine — detalle de costos
# ---------------------------------------------------------------------------

class WorkOrderLine(Base):
    """A single cost line: labour (is_part=False) or spare part (is_part=True).

    ``reception_detail_id`` is populated when the line originates from a
    mechanic's work log entry; it is NULL for extra charges or spare parts
    added directly on the work order.

    ``subtotal`` is stored explicitly so historical totals remain stable.
    """

    __tablename__ = "work_order_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_orders.id", name="fk_work_order_lines_work_order_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reception_detail_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "reception_details.id",
            name="fk_work_order_lines_reception_detail_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False, default=Decimal("1.000")
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_part: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    discount_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00"), server_default="0.00"
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    work_order: Mapped["WorkOrder"] = relationship(back_populates="lines")
    reception_detail: Mapped["ReceptionDetail | None"] = relationship(  # noqa: F821
        back_populates="work_order_lines", lazy="selectin"
    )
