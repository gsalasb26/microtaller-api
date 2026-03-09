"""receptions.py — Router para el módulo de Recepción de Vehículos.

Expone:
  GET    /receptions                — Listado paginado con filtros
  POST   /receptions/process        — Endpoint atómico "todo-en-uno" (ver docstring)
  GET    /receptions/{id}           — Detalle de una boleta
  POST   /receptions                — Crear boleta (para integraciones que ya saben los IDs)
  PATCH  /receptions/{id}           — Actualizar campos de la boleta
  PATCH  /receptions/{id}/status    — Transicionar el estado con validación de máquina de estados
  DELETE /receptions/{id}           — Eliminar boleta (solo en estado NEW)

Máquina de estados (ALLOWED_TRANSITIONS):
  NEW               → IN_PROGRESS
  IN_PROGRESS       → PAUSED, FINISHED
  PAUSED            → IN_PROGRESS, FINISHED
  FINISHED          → IN_PROGRESS  (re-apertura por ajuste)
  FINISHED          → WARRANTY_REVISION
  WARRANTY_REVISION → (terminal)
"""
import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.customer import Customer
from app.models.reception import Reception, ReceptionStatus
from app.models.reception_detail import ReceptionDetail
from app.models.vehicle import Vehicle
from app.schemas.reception import (
    ProcessReceptionInput,
    ProcessReceptionResult,
    ReceptionCreate,
    ReceptionList,
    ReceptionResponse,
    ReceptionUpdate,
)

router = APIRouter(prefix="/receptions", tags=["Receptions"])

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

#: Keys are the *current* status; values are the set of allowed *next* statuses.
ALLOWED_TRANSITIONS: dict[ReceptionStatus, set[ReceptionStatus]] = {
    ReceptionStatus.NEW: {
        ReceptionStatus.IN_PROGRESS,
    },
    ReceptionStatus.IN_PROGRESS: {
        ReceptionStatus.PAUSED,
        ReceptionStatus.FINISHED,
    },
    ReceptionStatus.PAUSED: {
        ReceptionStatus.IN_PROGRESS,
        ReceptionStatus.FINISHED,
    },
    ReceptionStatus.FINISHED: {
        ReceptionStatus.IN_PROGRESS,          # re-open for adjustment
        ReceptionStatus.WARRANTY_REVISION,    # escalate to warranty claim
    },
    ReceptionStatus.WARRANTY_REVISION: set(), # terminal — no outgoing transitions
}


def _assert_transition(current: ReceptionStatus, requested: ReceptionStatus) -> None:
    """Raise HTTP 422 if the requested status transition is not permitted.

    This is the single enforcement point for the reception lifecycle rules.
    Any code wanting to change ``current_status`` MUST call this function first.
    """
    if requested not in ALLOWED_TRANSITIONS[current]:
        allowed = [s.value for s in ALLOWED_TRANSITIONS[current]]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot transition from '{current.value}' to '{requested.value}'. "
                f"Allowed next states: {allowed or ['(none — terminal state)']}"
            ),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_404(db: AsyncSession, reception_id: UUID) -> Reception:
    r = await db.get(Reception, reception_id)
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Reception not found")
    return r


# ---------------------------------------------------------------------------
# POST /receptions/process  — Atomic "all-in-one" endpoint
#
# IMPORTANT: this route MUST be declared BEFORE /{reception_id} so that
# FastAPI does not interpret the literal path segment "process" as a UUID.
# ---------------------------------------------------------------------------

@router.post(
    "/process",
    response_model=ProcessReceptionResult,
    status_code=status.HTTP_201_CREATED,
    summary="Recibir vehículo (endpoint atómico)",
    description=(
        "Ejecuta en una sola transacción atómica: **upsert de cliente** (por cédula), "
        "**upsert de vehículo** (por placa) y **creación de boleta de recepción**. "
        "Si cualquier paso falla, se hace rollback total y se devuelve el error."
    ),
)
async def process_reception(
    payload: ProcessReceptionInput,
    db: AsyncSession = Depends(get_db),
) -> ProcessReceptionResult:
    """Atomic vehicle reception — three steps in one database transaction.

    Step 1 — Customer upsert
        Query ``customers`` by ``identification`` (cédula / passport).
        If found  → use existing ``id`` (no update, to preserve audit trail).
        If not    → INSERT new customer row.

    Step 2 — Vehicle upsert
        Query ``vehicles`` by ``plate``.
        If found  → UPDATE ``customer_id`` to the resolved owner and overwrite
                    ``vin_number`` if a new value was provided.
        If not    → INSERT new vehicle row linked to the resolved customer.

    Step 3 — Reception creation
        INSERT a new ``receptions`` row linking the resolved
        ``customer_id`` and ``vehicle_id``.

    Atomicity guarantee
        All three steps share a single ``session.begin()`` block.
        Any unhandled exception triggers an automatic rollback before
        the HTTP 400 / 422 / 500 response is returned to the caller.
    """
    try:
        async with db.begin():
            # ------------------------------------------------------------------
            # Step 1: Customer upsert by identification
            # ------------------------------------------------------------------
            customer_created = False
            customer = await db.scalar(
                select(Customer).where(
                    Customer.identification == payload.customer.identification
                )
            )
            if customer is None:
                customer = Customer(
                    id=uuid.uuid4(),
                    identification=payload.customer.identification,
                    name=payload.customer.name,
                    phone=payload.customer.phone,
                    email=payload.customer.email,
                    notes=payload.customer.notes,
                )
                db.add(customer)
                await db.flush()   # populate customer.id without committing
                customer_created = True

            # ------------------------------------------------------------------
            # Step 2: Vehicle upsert by plate
            # ------------------------------------------------------------------
            vehicle_created = False
            vehicle = await db.scalar(
                select(Vehicle).where(Vehicle.plate == payload.vehicle.plate.upper())
            )
            if vehicle is None:
                vehicle = Vehicle(
                    id=uuid.uuid4(),
                    customer_id=customer.id,
                    brand=payload.vehicle.brand,
                    model=payload.vehicle.model,
                    year=payload.vehicle.year,
                    plate=payload.vehicle.plate.upper(),
                    vehicle_type_id=payload.vehicle.vehicle_type_id,
                    vin_number=payload.vehicle.vin_number,
                )
                db.add(vehicle)
                await db.flush()
                vehicle_created = True
            else:
                # Transfer ownership to the current customer and refresh VIN if supplied
                vehicle.customer_id = customer.id
                if payload.vehicle.vin_number is not None:
                    vehicle.vin_number = payload.vehicle.vin_number
                await db.flush()

            # ------------------------------------------------------------------
            # Step 3: Create reception
            # ------------------------------------------------------------------
            reception = Reception(
                id=uuid.uuid4(),
                customer_id=customer.id,
                vehicle_id=vehicle.id,
                work_type_id=payload.work_type_id,
                reported_problem=payload.reported_problem,
                received_by=payload.received_by,
                mileage=payload.mileage,
                fuel_level=payload.fuel_level,
                vin_number=payload.vehicle.vin_number,
                current_status=ReceptionStatus.NEW,
            )
            db.add(reception)
            await db.flush()

            # ------------------------------------------------------------------
            # Step 4: Insert initial work items (if supplied)
            # ------------------------------------------------------------------
            now = datetime.now(timezone.utc)
            works = payload.initial_works or []
            for work in works:
                detail = ReceptionDetail(
                    id=uuid.uuid4(),
                    reception_id=reception.id,
                    work_type_id=work.work_type_id,
                    description=work.description,
                    work_date=work.work_date if work.work_date is not None else now,
                )
                db.add(detail)
            if works:
                await db.flush()

            # ------------------------------------------------------------------
            # Build result BEFORE the context manager commits so we can read IDs
            # ------------------------------------------------------------------
            result = ProcessReceptionResult(
                reception_id=reception.id,
                customer_id=customer.id,
                vehicle_id=vehicle.id,
                customer_created=customer_created,
                vehicle_created=vehicle_created,
                current_status=reception.current_status,
                details_created=len(works),
            )
        # async with db.begin() commits here on clean exit
        return result

    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integrity error during atomic reception: {exc.orig}",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unexpected error during atomic reception: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# GET /receptions — Paginated list with optional filters
# ---------------------------------------------------------------------------

@router.get("", response_model=ReceptionList)
async def list_receptions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    vehicle_id: UUID | None = Query(None, description="Filtrar por vehículo"),
    customer_id: UUID | None = Query(None, description="Filtrar por cliente"),
    current_status: ReceptionStatus | None = Query(None, description="Filtrar por estado"),
    db: AsyncSession = Depends(get_db),
):
    query = select(Reception)
    count_query = select(func.count()).select_from(Reception)

    filters = []
    if vehicle_id is not None:
        filters.append(Reception.vehicle_id == vehicle_id)
    if customer_id is not None:
        filters.append(Reception.customer_id == customer_id)
    if current_status is not None:
        filters.append(Reception.current_status == current_status)

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    total = await db.scalar(count_query)
    result = await db.execute(
        query.order_by(Reception.entry_at.desc()).offset(skip).limit(limit)
    )
    return ReceptionList(total=total, items=result.scalars().all())


# ---------------------------------------------------------------------------
# GET /receptions/{reception_id}
# ---------------------------------------------------------------------------

@router.get("/{reception_id}", response_model=ReceptionResponse)
async def get_reception(reception_id: UUID, db: AsyncSession = Depends(get_db)):
    return await _get_or_404(db, reception_id)


# ---------------------------------------------------------------------------
# POST /receptions — Create (for callers that already have customer/vehicle IDs)
# ---------------------------------------------------------------------------

@router.post("", response_model=ReceptionResponse, status_code=status.HTTP_201_CREATED)
async def create_reception(payload: ReceptionCreate, db: AsyncSession = Depends(get_db)):
    # Verify FK targets exist
    if not await db.get(Customer, payload.customer_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if not await db.get(Vehicle, payload.vehicle_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    reception = Reception(id=uuid.uuid4(), **payload.model_dump(), current_status=ReceptionStatus.NEW)
    db.add(reception)
    await db.commit()
    await db.refresh(reception)
    return reception


# ---------------------------------------------------------------------------
# PATCH /receptions/{reception_id} — Update mutable fields
# ---------------------------------------------------------------------------

@router.patch("/{reception_id}", response_model=ReceptionResponse)
async def update_reception(
    reception_id: UUID,
    payload: ReceptionUpdate,
    db: AsyncSession = Depends(get_db),
):
    reception = await _get_or_404(db, reception_id)

    data = payload.model_dump(exclude_unset=True)

    # Status changes via the /status sub-resource are preferred, but if
    # current_status is included here we still validate the transition.
    if "current_status" in data:
        _assert_transition(reception.current_status, data["current_status"])

    for field, value in data.items():
        setattr(reception, field, value)

    await db.commit()
    await db.refresh(reception)
    return reception


# ---------------------------------------------------------------------------
# PATCH /receptions/{reception_id}/status — Explicit state-machine transition
# ---------------------------------------------------------------------------

@router.patch(
    "/{reception_id}/status",
    response_model=ReceptionResponse,
    summary="Transicionar estado de la recepción",
)
async def transition_status(
    reception_id: UUID,
    new_status: ReceptionStatus = Query(..., description="Estado destino"),
    db: AsyncSession = Depends(get_db),
):
    """Apply a validated state-machine transition.

    Enforces ALLOWED_TRANSITIONS; returns HTTP 422 if the
    requested transition is not permitted from the current state.
    """
    reception = await _get_or_404(db, reception_id)
    _assert_transition(reception.current_status, new_status)
    reception.current_status = new_status
    await db.commit()
    await db.refresh(reception)
    return reception


# ---------------------------------------------------------------------------
# DELETE /receptions/{reception_id}
# ---------------------------------------------------------------------------

@router.delete("/{reception_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reception(reception_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete a reception.  Only allowed when status is NEW (not yet in progress)."""
    reception = await _get_or_404(db, reception_id)
    if reception.current_status != ReceptionStatus.NEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete a reception in state '{reception.current_status.value}'. "
                "Only NEW receptions can be deleted."
            ),
        )
    await db.delete(reception)
    await db.commit()
