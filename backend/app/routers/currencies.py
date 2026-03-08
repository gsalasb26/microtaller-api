from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.currency import Currency
from app.schemas.currency import (
    CurrencyCreate,
    CurrencyList,
    CurrencyResponse,
    CurrencyUpdate,
)

router = APIRouter(prefix="/currencies", tags=["Currencies"])


@router.get("", response_model=CurrencyList)
async def list_currencies(
    db: AsyncSession = Depends(get_db),
):
    """Return all currencies ordered by ISO code."""
    total = await db.scalar(select(func.count()).select_from(Currency))
    result = await db.execute(select(Currency).order_by(Currency.code))
    return CurrencyList(total=total or 0, items=list(result.scalars().all()))


@router.get("/{currency_id}", response_model=CurrencyResponse)
async def get_currency(
    currency_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    currency = await db.get(Currency, currency_id)
    if not currency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currency not found")
    return currency


@router.post("", response_model=CurrencyResponse, status_code=status.HTTP_201_CREATED)
async def create_currency(
    payload: CurrencyCreate,
    db: AsyncSession = Depends(get_db),
):
    # Check for duplicate code (case-insensitive) or name
    conflict = await db.scalar(
        select(Currency).where(
            Currency.code.ilike(payload.code) | Currency.name.ilike(payload.name)
        )
    )
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A currency with that code or name already exists",
        )
    currency = Currency(**payload.model_dump())
    db.add(currency)
    await db.flush()
    await db.refresh(currency)
    return currency


@router.patch("/{currency_id}", response_model=CurrencyResponse)
async def update_currency(
    currency_id: UUID,
    payload: CurrencyUpdate,
    db: AsyncSession = Depends(get_db),
):
    currency = await db.get(Currency, currency_id)
    if not currency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currency not found")

    data = payload.model_dump(exclude_unset=True)
    if data:
        conditions = []
        if "code" in data:
            conditions.append(Currency.code.ilike(data["code"]))
        if "name" in data:
            conditions.append(Currency.name.ilike(data["name"]))
        if conditions:
            from sqlalchemy import or_
            conflict = await db.scalar(
                select(Currency).where(
                    or_(*conditions), Currency.id != currency_id
                )
            )
            if conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A currency with that code or name already exists",
                )
    for field, value in data.items():
        setattr(currency, field, value)
    await db.flush()
    await db.refresh(currency)
    return currency


@router.delete("/{currency_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_currency(
    currency_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    currency = await db.get(Currency, currency_id)
    if not currency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currency not found")
    await db.delete(currency)
