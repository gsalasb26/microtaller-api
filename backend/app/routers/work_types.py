from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.work_type import WorkType
from app.schemas.work_type import WorkTypeCreate, WorkTypeList, WorkTypeResponse, WorkTypeUpdate

router = APIRouter(prefix="/work-types", tags=["Work Types"])


@router.get("", response_model=WorkTypeList)
async def list_work_types(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    total = await db.scalar(select(func.count()).select_from(WorkType))
    result = await db.execute(
        select(WorkType).order_by(WorkType.name).offset(skip).limit(limit)
    )
    return WorkTypeList(total=total, items=result.scalars().all())


@router.get("/{work_type_id}", response_model=WorkTypeResponse)
async def get_work_type(work_type_id: UUID, db: AsyncSession = Depends(get_db)):
    wt = await db.get(WorkType, work_type_id)
    if not wt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Work type not found")
    return wt


@router.post("", response_model=WorkTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_work_type(payload: WorkTypeCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(
        select(WorkType).where(WorkType.name.ilike(payload.name))
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Work type name already exists")
    wt = WorkType(**payload.model_dump())
    db.add(wt)
    await db.commit()
    await db.refresh(wt)
    return wt


@router.patch("/{work_type_id}", response_model=WorkTypeResponse)
async def update_work_type(
    work_type_id: UUID,
    payload: WorkTypeUpdate,
    db: AsyncSession = Depends(get_db),
):
    wt = await db.get(WorkType, work_type_id)
    if not wt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Work type not found")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        clash = await db.scalar(
            select(WorkType).where(WorkType.name.ilike(data["name"]), WorkType.id != work_type_id)
        )
        if clash:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Work type name already exists")

    for field, value in data.items():
        setattr(wt, field, value)

    await db.commit()
    await db.refresh(wt)
    return wt


@router.delete("/{work_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_type(work_type_id: UUID, db: AsyncSession = Depends(get_db)):
    wt = await db.get(WorkType, work_type_id)
    if not wt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Work type not found")
    try:
        await db.delete(wt)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Cannot delete: work type is referenced by one or more receptions",
        )
