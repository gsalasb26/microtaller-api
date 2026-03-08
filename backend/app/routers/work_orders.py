from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.vehicle import Vehicle
from app.models.work_order import OrderStatus, WorkOrder, WorkOrderItem
from app.schemas.work_order import (
    WorkOrderCreate,
    WorkOrderItemCreate,
    WorkOrderItemResponse,
    WorkOrderItemUpdate,
    WorkOrderList,
    WorkOrderResponse,
    WorkOrderUpdate,
)

router = APIRouter(prefix="/work-orders", tags=["Work Orders"])

_CENT = Decimal("0.01")

# ---------------------------------------------------------------------------
# Status-transition guard
# ---------------------------------------------------------------------------

#: Keys are the *current* status; values are the set of allowed *next* statuses.
ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.received: {OrderStatus.in_progress, OrderStatus.delivered},
    OrderStatus.in_progress: {OrderStatus.delivered},
    OrderStatus.delivered: set(),  # terminal
}


def _assert_transition(current: OrderStatus, requested: OrderStatus) -> None:
    """Raise 422 if the requested status transition is not allowed."""
    if requested not in ALLOWED_TRANSITIONS[current]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot transition from '{current.value}' to '{requested.value}'. "
                f"Allowed next states: {[s.value for s in ALLOWED_TRANSITIONS[current]]}"
            ),
        )


def _total(quantity: Decimal, unit_price: Decimal) -> Decimal:
    """Compute line total rounded to 2 decimal places."""
    return (quantity * unit_price).quantize(_CENT, rounding=ROUND_HALF_UP)


# -- Work Orders CRUD ---------------------------------------------------------

@router.get("", response_model=WorkOrderList)
async def list_work_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    vehicle_id: UUID | None = Query(None, description="Filter by vehicle"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    db: AsyncSession = Depends(get_db),
):
    query = select(WorkOrder)
    count_query = select(func.count()).select_from(WorkOrder)

    filters = []
    if vehicle_id is not None:
        filters.append(WorkOrder.vehicle_id == vehicle_id)
    if status_filter is not None:
        filters.append(WorkOrder.status == status_filter)

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    total = await db.scalar(count_query)
    result = await db.execute(
        query.order_by(WorkOrder.created_at.desc()).offset(skip).limit(limit)
    )
    work_orders = result.scalars().all()
    return WorkOrderList(total=total or 0, items=list(work_orders))


@router.get("/open", response_model=WorkOrderList)
async def list_open_work_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Return all work orders that have not been delivered yet."""
    query = select(WorkOrder).where(WorkOrder.status != OrderStatus.delivered)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(WorkOrder.created_at.desc()).offset(skip).limit(limit)
    )
    return WorkOrderList(total=total or 0, items=list(result.scalars().all()))


@router.get("/by-plate/{plate}", response_model=WorkOrderList)
async def list_work_orders_by_plate(
    plate: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Return all work orders for the vehicle matching the given licence plate."""
    vehicle = await db.scalar(select(Vehicle).where(Vehicle.plate.ilike(plate)))
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No vehicle found with plate '{plate}'",
        )
    query = select(WorkOrder).where(WorkOrder.vehicle_id == vehicle.id)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(WorkOrder.created_at.desc()).offset(skip).limit(limit)
    )
    return WorkOrderList(total=total or 0, items=list(result.scalars().all()))


@router.get("/{work_order_id}", response_model=WorkOrderResponse)
async def get_work_order(
    work_order_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    work_order = await db.get(WorkOrder, work_order_id)
    if not work_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    return work_order


@router.post("", response_model=WorkOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_work_order(
    payload: WorkOrderCreate,
    db: AsyncSession = Depends(get_db),
):
    vehicle = await db.get(Vehicle, payload.vehicle_id)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle {payload.vehicle_id} not found",
        )

    work_order = WorkOrder(**payload.model_dump(exclude={"items"}))
    db.add(work_order)
    await db.flush()  # obtain work_order.id before inserting items

    for item_in in payload.items:
        db.add(WorkOrderItem(
            work_order_id=work_order.id,
            description=item_in.description,
            quantity=item_in.quantity,
            unit_price=item_in.unit_price,
            total=_total(item_in.quantity, item_in.unit_price),
        ))

    await db.flush()
    await db.refresh(work_order)
    return work_order


@router.patch("/{work_order_id}", response_model=WorkOrderResponse)
async def update_work_order(
    work_order_id: UUID,
    payload: WorkOrderUpdate,
    db: AsyncSession = Depends(get_db),
):
    work_order = await db.get(WorkOrder, work_order_id)
    if not work_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")

    updates = payload.model_dump(exclude_unset=True)

    # Enforce status-transition rules when the caller changes status
    if "status" in updates:
        _assert_transition(
            current=work_order.status,
            requested=updates["status"],
        )

    for field, value in updates.items():
        setattr(work_order, field, value)
    await db.flush()
    await db.refresh(work_order)
    return work_order


@router.delete("/{work_order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_order(
    work_order_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    work_order = await db.get(WorkOrder, work_order_id)
    if not work_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    await db.delete(work_order)


@router.post("/{work_order_id}/close", response_model=WorkOrderResponse)
async def close_work_order(
    work_order_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Mark a work order as delivered.

    Business rules enforced:
    - The work order must have at least one item.
    - The current status must allow a transition to `delivered`.
    """
    work_order = await db.get(WorkOrder, work_order_id)
    if not work_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")

    # Must have items before closing
    item_count = await db.scalar(
        select(func.count())
        .where(WorkOrderItem.work_order_id == work_order_id)
    )
    if not item_count:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot close a work order with no items. Add at least one item first.",
        )

    _assert_transition(work_order.status, OrderStatus.delivered)

    work_order.status = OrderStatus.delivered
    work_order.closed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(work_order)
    return work_order


# -- Work Order Items CRUD ----------------------------------------------------

@router.post(
    "/{work_order_id}/items",
    response_model=WorkOrderItemResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Work Order Items"],
)
async def add_item(
    work_order_id: UUID,
    payload: WorkOrderItemCreate,
    db: AsyncSession = Depends(get_db),
):
    if not await db.get(WorkOrder, work_order_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    item = WorkOrderItem(
        work_order_id=work_order_id,
        description=payload.description,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        total=_total(payload.quantity, payload.unit_price),
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.patch(
    "/{work_order_id}/items/{item_id}",
    response_model=WorkOrderItemResponse,
    tags=["Work Order Items"],
)
async def update_item(
    work_order_id: UUID,
    item_id: UUID,
    payload: WorkOrderItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(WorkOrderItem, item_id)
    if not item or item.work_order_id != work_order_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    # Recalculate total whenever quantity or unit_price changes
    item.total = _total(item.quantity, item.unit_price)
    await db.flush()
    await db.refresh(item)
    return item


@router.delete(
    "/{work_order_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Work Order Items"],
)
async def delete_item(
    work_order_id: UUID,
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(WorkOrderItem, item_id)
    if not item or item.work_order_id != work_order_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    await db.delete(item)
