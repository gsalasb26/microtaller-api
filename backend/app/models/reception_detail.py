"""reception_detail.py — Línea de trabajo realizado dentro de una boleta de recepción.

Cada Reception puede tener N ReceptionDetail, uno por cada trabajo específico
ejecutado (cambio de aceite, alineación, etc.).

Auditoría:
  - created_at : inmutable — se llena con func.now() al hacer INSERT.
  - updated_at : se actualiza automáticamente vía Python-side onupdate en cada
                 llamada ORM que modifica la fila.
  - work_date  : fecha efectiva del trabajo.  Si no se provee en la entrada,
                 el router lo establece igual a la hora de creación.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReceptionDetail(Base):
    """A single work item performed during a vehicle reception."""

    __tablename__ = "reception_details"
    __table_args__ = (
        Index("ix_reception_details_reception_id", "reception_id"),
        Index("ix_reception_details_work_type_id", "work_type_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- Foreign keys --------------------------------------------------------
    reception_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("receptions.id", name="fk_reception_details_reception_id", ondelete="CASCADE"),
        nullable=False,
    )
    work_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_types.id", name="fk_reception_details_work_type_id", ondelete="RESTRICT"),
        nullable=False,
    )

    # --- Detail fields -------------------------------------------------------
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),   # Python-side: SQLAlchemy injects func.now() on UPDATE
        nullable=False,
    )
    # Effective work date — defaults to created_at when not supplied (set in router)
    work_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # --- Relationships -------------------------------------------------------
    reception: Mapped["Reception"] = relationship(  # noqa: F821
        back_populates="details", lazy="selectin"
    )
    work_type: Mapped["WorkType"] = relationship(  # noqa: F821
        lazy="selectin"
    )
    work_order_lines: Mapped[list["WorkOrderLine"]] = relationship(  # noqa: F821
        back_populates="reception_detail", lazy="selectin"
    )
