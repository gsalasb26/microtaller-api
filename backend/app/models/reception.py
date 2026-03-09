"""reception.py — Boleta de recepción de vehículo.

Representa el ingreso físico de un vehículo al taller.
Es el punto de entrada al flujo operativo:

    NEW → IN_PROGRESS ↔ PAUSED
                ↓
            FINISHED → IN_PROGRESS   (re-apertura por ajuste)
            FINISHED → WARRANTY_REVISION

Restricciones:
  - FINISHED / WARRANTY_REVISION → NEW  está prohibido.
  - WARRANTY_REVISION es un estado especial terminal para reclamos de garantía.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# FuelLevel enum
# ---------------------------------------------------------------------------

class FuelLevel(str, enum.Enum):
    """Standardised fuel-level readings stored in the receptions table.

    The **value** (e.g. ``QUARTER``) is what PostgreSQL stores.
    Use ``.label`` for the human-readable display string.
    """

    EMPTY          = "EMPTY"           # Vacío / Reserva
    QUARTER        = "QUARTER"         # 1/4
    HALF           = "HALF"            # 1/2
    THREE_QUARTERS = "THREE_QUARTERS"  # 3/4
    FULL           = "FULL"            # Lleno

    @property
    def label(self) -> str:  # noqa: D102 — human-readable string
        return {
            FuelLevel.EMPTY:          "Vacío / Reserva",
            FuelLevel.QUARTER:        "1/4",
            FuelLevel.HALF:           "1/2",
            FuelLevel.THREE_QUARTERS: "3/4",
            FuelLevel.FULL:           "Lleno",
        }[self]


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

class ReceptionStatus(str, enum.Enum):
    """Lifecycle states for a vehicle reception.

    Allowed transitions (see ALLOWED_TRANSITIONS in receptions.py):
      NEW               → IN_PROGRESS
      IN_PROGRESS       → PAUSED, FINISHED
      PAUSED            → IN_PROGRESS, FINISHED
      FINISHED          → IN_PROGRESS (re-open for adjustment), WARRANTY_REVISION
      WARRANTY_REVISION → (terminal — no outgoing transitions)
    """

    NEW               = "NEW"
    IN_PROGRESS       = "IN_PROGRESS"
    PAUSED            = "PAUSED"
    FINISHED          = "FINISHED"
    WARRANTY_REVISION = "WARRANTY_REVISION"


# ---------------------------------------------------------------------------
# Reception model
# ---------------------------------------------------------------------------

class Reception(Base):
    """Workshop intake form — one row per vehicle visit."""

    __tablename__ = "receptions"
    __table_args__ = (
        Index("ix_receptions_vehicle_id_entry_at", "vehicle_id", "entry_at"),
        Index("ix_receptions_current_status_entry_at", "current_status", "entry_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- Foreign keys --------------------------------------------------------
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", name="fk_receptions_customer_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", name="fk_receptions_vehicle_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    work_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_types.id", name="fk_receptions_work_type_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # --- Reception fields ----------------------------------------------------
    reported_problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    received_by: Mapped[str] = mapped_column(String(100), nullable=False)
    mileage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fuel_level: Mapped[FuelLevel | None] = mapped_column(
        Enum(FuelLevel, name="fuel_level"),
        nullable=True,
    )
    vin_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    current_status: Mapped[ReceptionStatus] = mapped_column(
        Enum(ReceptionStatus, name="reception_status"),
        nullable=False,
        default=ReceptionStatus.NEW,
        server_default=ReceptionStatus.NEW.value,
        index=True,
    )

    # --- Relationships -------------------------------------------------------
    customer: Mapped["Customer"] = relationship(  # noqa: F821
        back_populates="receptions", lazy="selectin"
    )
    vehicle: Mapped["Vehicle"] = relationship(  # noqa: F821
        back_populates="receptions", lazy="selectin"
    )
    work_type: Mapped["WorkType"] = relationship(
        back_populates="receptions", lazy="selectin"
    )
    details: Mapped[list["ReceptionDetail"]] = relationship(  # noqa: F821
        back_populates="reception",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="ReceptionDetail.work_date",
    )
    work_orders: Mapped[list["WorkOrder"]] = relationship(  # noqa: F821
        back_populates="reception", lazy="selectin"
    )
