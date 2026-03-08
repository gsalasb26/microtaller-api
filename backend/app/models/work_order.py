import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrderStatus(str, enum.Enum):
    """Lifecycle states for a work order.

    Allowed transitions:
      received   -> in_progress  (work started)
      received   -> delivered    (simple job, no intermediate step needed)
      in_progress -> delivered   (job completed)
    delivered is the only terminal state.
    """

    received    = "received"     # Vehicle checked in, awaiting work
    in_progress = "in_progress"  # Actively being worked on
    delivered   = "delivered"    # Returned to customer — terminal


class WorkOrder(Base):
    """A repair or service job opened for a specific vehicle."""

    __tablename__ = "work_orders"
    __table_args__ = (
        Index("ix_work_orders_vehicle_id_created_at", "vehicle_id", "created_at"),
        Index("ix_work_orders_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"),
        nullable=False,
        default=OrderStatus.received,
        index=True,
    )
    checkin_photos: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Relationships -------------------------------------------------------
    vehicle: Mapped["Vehicle"] = relationship(  # noqa: F821
        back_populates="work_orders", lazy="selectin"
    )
    items: Mapped[list["WorkOrderItem"]] = relationship(
        back_populates="work_order",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="WorkOrderItem.id",
    )


class WorkOrderItem(Base):
    """A single line on a work order: labour, part, or any other charge."""

    __tablename__ = "work_order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_wo_items_qty_positive"),
        CheckConstraint("unit_price >= 0", name="ck_wo_items_price_non_negative"),
        CheckConstraint("total >= 0", name="ck_wo_items_total_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    currency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("currencies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # --- Relationships -------------------------------------------------------
    work_order: Mapped["WorkOrder"] = relationship(back_populates="items")
    currency: Mapped["Currency"] = relationship(  # noqa: F821
        back_populates="work_order_items", lazy="selectin"
    )