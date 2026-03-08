import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VehicleType(Base):
    """Catalogue of vehicle types (e.g. Sedan, SUV, Pickup, Motorcycle)."""

    __tablename__ = "vehicle_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(80), nullable=False, unique=True, index=True
    )

    # Relationships
    vehicles: Mapped[list["Vehicle"]] = relationship(  # noqa: F821
        back_populates="vehicle_type", lazy="selectin"
    )
