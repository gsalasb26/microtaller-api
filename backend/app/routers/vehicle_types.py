from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.vehicle_type import VehicleType
from app.schemas.vehicle_type import (
    VehicleTypeCreate,
    VehicleTypeList,
    VehicleTypeResponse,
    VehicleTypeUpdate,
)

router = APIRouter(prefix="/vehicle-types", tags=["Vehicle Types"])


@router.get("", response_model=VehicleTypeList)
async def list_vehicle_types(
    db: AsyncSession = Depends(get_db),
):
    """Return all vehicle types ordered alphabetically."""
    total = await db.scalar(select(func.count()).select_from(VehicleType))
    result = await db.execute(select(VehicleType).order_by(VehicleType.name))
    return VehicleTypeList(total=total or 0, items=list(result.scalars().all()))


@router.get("/{vehicle_type_id}", response_model=VehicleTypeResponse)
async def get_vehicle_type(
    vehicle_type_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    vt = await db.get(VehicleType, vehicle_type_id)
    if not vt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle type not found")
    return vt


@router.post("", response_model=VehicleTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_vehicle_type(
    payload: VehicleTypeCreate,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(
        select(VehicleType).where(VehicleType.name.ilike(payload.name))
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A vehicle type named '{payload.name}' already exists",
        )
    vt = VehicleType(**payload.model_dump())
    db.add(vt)
    await db.flush()
    await db.refresh(vt)
    return vt


@router.patch("/{vehicle_type_id}", response_model=VehicleTypeResponse)
async def update_vehicle_type(
    vehicle_type_id: UUID,
    payload: VehicleTypeUpdate,
    db: AsyncSession = Depends(get_db),
):
    vt = await db.get(VehicleType, vehicle_type_id)
    if not vt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle type not found")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"].lower() != vt.name.lower():
        conflict = await db.scalar(
            select(VehicleType).where(VehicleType.name.ilike(data["name"]))
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A vehicle type named '{data['name']}' already exists",
            )
    for field, value in data.items():
        setattr(vt, field, value)
    await db.flush()
    await db.refresh(vt)
    return vt


@router.delete("/{vehicle_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle_type(
    vehicle_type_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    vt = await db.get(VehicleType, vehicle_type_id)
    if not vt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle type not found")
    await db.delete(vt)
