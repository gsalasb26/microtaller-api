from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db
from app.models.vehicle import Vehicle
from app.schemas.vehicle import (
    VehicleCreate,
    VehicleList,
    VehicleResponse,
    VehicleUpdate,
)

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.get("/by-plate/{plate}", response_model=VehicleResponse)
async def get_vehicle_by_plate(
    plate: str,
    db: AsyncSession = Depends(get_db),
):
    """Look up a vehicle by its licence plate (exact match, case-insensitive)."""
    vehicle = await db.scalar(
        select(Vehicle).where(Vehicle.plate.ilike(plate))
    )
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No vehicle found with plate '{plate}'",
        )
    return vehicle


@router.get("", response_model=VehicleList)
async def list_vehicles(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    customer_id: UUID | None = Query(None, description="Filter by customer"),
    db: AsyncSession = Depends(get_db),
):
    query = select(Vehicle)
    count_query = select(func.count()).select_from(Vehicle)
    if customer_id is not None:
        query = query.where(Vehicle.customer_id == customer_id)
        count_query = count_query.where(Vehicle.customer_id == customer_id)

    total = await db.scalar(count_query)
    result = await db.execute(
        query.order_by(Vehicle.brand, Vehicle.model).offset(skip).limit(limit)
    )
    items = result.scalars().all()
    return VehicleList(total=total or 0, items=list(items))


@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(
    vehicle_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    vehicle = await db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    return vehicle


@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    payload: VehicleCreate,
    db: AsyncSession = Depends(get_db),
):
    # Check for duplicate plate
    existing = await db.scalar(
        select(Vehicle).where(Vehicle.plate == payload.plate)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A vehicle with plate '{payload.plate}' already exists",
        )
    vehicle = Vehicle(**payload.model_dump())
    db.add(vehicle)
    await db.flush()
    await db.refresh(vehicle)
    return vehicle


@router.patch("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: UUID,
    payload: VehicleUpdate,
    db: AsyncSession = Depends(get_db),
):
    vehicle = await db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    data = payload.model_dump(exclude_unset=True)
    if "plate" in data and data["plate"] != vehicle.plate:
        existing = await db.scalar(
            select(Vehicle).where(Vehicle.plate == data["plate"])
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A vehicle with plate '{data['plate']}' already exists",
            )
    for field, value in data.items():
        setattr(vehicle, field, value)
    await db.flush()
    await db.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    vehicle_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    vehicle = await db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    await db.delete(vehicle)
