"""reception.py — Schemas Pydantic para el módulo de Recepción.

Incluye los schemas estándar CRUD más el schema especial
ProcessReceptionInput / ProcessReceptionResult para el endpoint
atómico POST /receptions/process.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.reception import FuelLevel, ReceptionStatus
from app.schemas.reception_detail import ReceptionDetailBase, ReceptionDetailResponse
from app.schemas.work_type import WorkTypeResponse


# ── Base ──────────────────────────────────────────────────────────────────────
class ReceptionBase(BaseModel):
    customer_id: UUID
    vehicle_id: UUID
    work_type_id: UUID | None = None
    reported_problem: str | None = Field(None, max_length=2000)
    received_by: str = Field(..., min_length=1, max_length=100)
    mileage: int | None = Field(None, ge=0)
    fuel_level: FuelLevel | None = None
    vin_number: str | None = Field(None, min_length=1, max_length=50)


# ── Create ────────────────────────────────────────────────────────────────────
class ReceptionCreate(ReceptionBase):
    pass


# ── Update ────────────────────────────────────────────────────────────────────
class ReceptionUpdate(BaseModel):
    """All fields optional for PATCH semantics."""

    work_type_id: UUID | None = None
    reported_problem: str | None = Field(None, max_length=2000)
    received_by: str | None = Field(None, min_length=1, max_length=100)
    mileage: int | None = Field(None, ge=0)
    fuel_level: FuelLevel | None = None
    vin_number: str | None = Field(None, min_length=1, max_length=50)
    current_status: ReceptionStatus | None = None


# ── Response ──────────────────────────────────────────────────────────────────
class ReceptionResponse(ReceptionBase):
    id: UUID
    current_status: ReceptionStatus
    entry_at: datetime
    work_type: WorkTypeResponse | None = None
    details: list[ReceptionDetailResponse] = []

    model_config = {"from_attributes": True}


class ReceptionList(BaseModel):
    total: int
    items: list[ReceptionResponse]


# ── Atomic process endpoint ───────────────────────────────────────────────────

class ProcessCustomerInput(BaseModel):
    """Customer data for upsert during atomic reception processing.

    The ``identification`` field (cédula / passport) is the natural business
    key used to decide whether to INSERT or SELECT an existing customer.
    """

    identification: str = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Cédula o pasaporte — clave de negocio para el upsert",
    )
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=1, max_length=20)
    email: str | None = Field(None, max_length=150)
    notes: str | None = Field(None, max_length=500)


class ProcessVehicleInput(BaseModel):
    """Vehicle data for upsert during atomic reception processing.

    The ``plate`` is the natural business key.  If the vehicle already
    exists, ``customer_id`` (resolved from the upsert above) and
    ``vin_number`` will be updated in place.
    """

    plate: str = Field(..., min_length=1, max_length=20)
    brand: str = Field(..., min_length=1, max_length=80)
    model: str = Field(..., min_length=1, max_length=80)
    year: int = Field(..., ge=1900, le=2100)
    vehicle_type_id: UUID | None = None
    vin_number: str | None = Field(
        None,
        min_length=1,
        max_length=50,
        description="Se actualiza en el vehículo existente si se provee",
    )


class ProcessReceptionInput(BaseModel):
    """All-in-one payload for POST /receptions/process.

    Combines customer upsert, vehicle upsert, reception creation, and
    optional initial work items in a single atomic transaction.
    """

    customer: ProcessCustomerInput
    vehicle: ProcessVehicleInput
    work_type_id: UUID | None = None
    reported_problem: str | None = Field(None, max_length=2000)
    received_by: str = Field(..., min_length=1, max_length=100)
    mileage: int | None = Field(None, ge=0)
    fuel_level: str | None = Field(None, max_length=20, examples=["Full", "3/4", "1/2", "1/4", "Reserve"])
    initial_works: list[ReceptionDetailBase] | None = Field(
        None,
        description="Trabajos iniciales opcionales. Puede omitirse, enviarse como null o como lista vacía.",
    )


class ProcessReceptionResult(BaseModel):
    """Response returned by POST /receptions/process."""

    reception_id: UUID
    customer_id: UUID
    vehicle_id: UUID
    customer_created: bool = Field(description="True si el cliente fue creado; False si ya existía")
    vehicle_created: bool = Field(description="True si el vehículo fue creado; False si ya existía")
    current_status: ReceptionStatus
    details_created: int = Field(description="Cantidad de trabajos insertados desde initial_works")

    model_config = {"from_attributes": False}
