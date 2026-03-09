"""work_type.py — Catálogo de motivos de visita al taller.

Ejemplos: Mantenimiento preventivo, Falla mecánica, Revisión eléctrica, Garantía.
"""
import uuid

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WorkType(Base):
    """Look-up table for the type/reason of a workshop reception.

    Kept simple on purpose: name is the business key.
    """

    __tablename__ = "work_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(80), nullable=False, unique=True, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    receptions: Mapped[list["Reception"]] = relationship(  # noqa: F821
        back_populates="work_type", lazy="selectin"
    )
