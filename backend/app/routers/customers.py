from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db
from app.models.customer import Customer
from app.schemas.customer import (
    CustomerCreate,
    CustomerList,
    CustomerResponse,
    CustomerUpdate,
)

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("/search", response_model=CustomerList)
async def search_customers(
    q: str = Query(..., min_length=1, description="Search term matched against name, phone, and email"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search across name, phone and email (case-insensitive)."""
    term = f"%{q}%"
    query = select(Customer).where(
        (Customer.name.ilike(term))
        | (Customer.phone.ilike(term))
        | (Customer.email.ilike(term))
    )
    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total = await db.scalar(count_query)
    result = await db.execute(
        query.order_by(Customer.name).offset(skip).limit(limit)
    )
    return CustomerList(total=total or 0, items=list(result.scalars().all()))


@router.get("", response_model=CustomerList)
async def list_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    total = await db.scalar(select(func.count()).select_from(Customer))
    result = await db.execute(
        select(Customer).order_by(Customer.name).offset(skip).limit(limit)
    )
    items = result.scalars().all()
    return CustomerList(total=total or 0, items=list(items))


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreate,
    db: AsyncSession = Depends(get_db),
):
    customer = Customer(**payload.model_dump())
    db.add(customer)
    await db.flush()
    await db.refresh(customer)
    return customer


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(customer, field, value)
    await db.flush()
    await db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    await db.delete(customer)
