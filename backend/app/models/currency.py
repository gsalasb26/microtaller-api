import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Currency(Base):
    """ISO-4217 currency catalogue (e.g. USD, EUR, MXN)."""

    __tablename__ = "currencies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(80), nullable=False, unique=True, index=True
    )
    code: Mapped[str] = mapped_column(
        String(3), nullable=False, unique=True, index=True
    )
    symbol: Mapped[str] = mapped_column(String(5), nullable=False)

    # Relationships
    work_order_items: Mapped[list["WorkOrderItem"]] = relationship(  # noqa: F821
        back_populates="currency", lazy="selectin"
    )
