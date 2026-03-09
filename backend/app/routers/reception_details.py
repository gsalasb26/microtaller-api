"""reception_details.py — Router independiente para trabajos realizados en una recepción.

Expone:
  POST  /reception-details/       — Registrar un trabajo en una boleta ya existente
  PATCH /reception-details/{id}   — Editar description y/o work_date de un trabajo

Regla de auditoría:
  - Si ``work_date`` no se envía en el POST, se asigna la fecha/hora actual (UTC).
  - ``updated_at`` se refresca automáticamente en cada PATCH.
  - ``created_at``, ``reception_id`` y ``work_type_id`` son inmutables.
"""
import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.reception import Reception
from app.models.reception_detail import ReceptionDetail
from app.models.work_type import WorkType
from app.schemas.reception_detail import (
    ReceptionDetailCreate,
    ReceptionDetailResponse,
    ReceptionDetailUpdate,
)

router = APIRouter(prefix="/reception-details", tags=["Reception Details"])


# ---------------------------------------------------------------------------
# POST /reception-details/
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ReceptionDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar trabajo en una boleta existente",
    description=(
        "Agrega un trabajo individual a una boleta de recepción ya creada. "
        "Si ``work_date`` se omite o llega como ``null``, se usa la fecha y hora actual."
    ),
)
async def create_reception_detail(
    payload: ReceptionDetailCreate,
    db: AsyncSession = Depends(get_db),
) -> ReceptionDetailResponse:
    """Add a single work item to an existing reception.

    Validates that both the referenced ``reception_id`` and ``work_type_id``
    exist before inserting.  If ``work_date`` is not supplied the current UTC
    timestamp is used so the audit trail is always populated.
    """
    # Verify reception exists
    reception = await db.get(Reception, payload.reception_id)
    if not reception:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Reception '{payload.reception_id}' not found",
        )

    # Verify work_type exists
    work_type = await db.get(WorkType, payload.work_type_id)
    if not work_type:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"WorkType '{payload.work_type_id}' not found",
        )

    now = datetime.now(timezone.utc)
    detail = ReceptionDetail(
        id=uuid.uuid4(),
        reception_id=payload.reception_id,
        work_type_id=payload.work_type_id,
        description=payload.description,
        work_date=payload.work_date if payload.work_date is not None else now,
    )
    db.add(detail)
    await db.commit()
    await db.refresh(detail)
    return detail


# ---------------------------------------------------------------------------
# PATCH /reception-details/{detail_id}
# ---------------------------------------------------------------------------

@router.patch(
    "/{detail_id}",
    response_model=ReceptionDetailResponse,
    summary="Editar un trabajo realizado",
    description=(
        "Permite modificar únicamente ``description`` y/o ``work_date``. "
        "Si ``work_date`` se envía como ``null`` se asigna la fecha y hora actual. "
        "``updated_at`` se refresca automáticamente en cada llamada."
    ),
)
async def update_reception_detail(
    detail_id: UUID,
    payload: ReceptionDetailUpdate,
    db: AsyncSession = Depends(get_db),
) -> ReceptionDetailResponse:
    """Partial update for a ReceptionDetail row.

    Editable fields: ``description``, ``work_date``.
    Immutable fields: ``id``, ``reception_id``, ``work_type_id``, ``created_at``.

    If the client sends ``"work_date": null`` the field is set to *now*,
    preserving the invariant that work_date is never NULL in the database.
    """
    detail = await db.get(ReceptionDetail, detail_id)
    if not detail:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Reception detail not found")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields provided to update",
        )

    now = datetime.now(timezone.utc)

    # Apply description if provided
    if "description" in data:
        detail.description = data["description"]

    # work_date: explicit null → use now; explicit datetime → use it
    if "work_date" in data:
        detail.work_date = data["work_date"] if data["work_date"] is not None else now

    # Always refresh updated_at — guarantees the column changes even when the
    # client only sends a field whose value happens to equal the stored value.
    detail.updated_at = now

    await db.commit()
    await db.refresh(detail)
    return detail
