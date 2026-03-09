"""routers/work_orders.py — CRUD + atomic process endpoint for WorkOrder.

Endpoints
---------
GET    /work-orders                  — paginated list (filterable)
GET    /work-orders/{id}             — single detail
POST   /work-orders                  — create with lines
PATCH  /work-orders/{id}             — update mutable fields
DELETE /work-orders/{id}             — remove (only DRAFT / CANCELLED)
PATCH  /work-orders/{id}/status      — lifecycle transition
PATCH  /work-orders/{id}/cancel      — cancel OT and revert reception to IN_PROGRESS
POST   /work-orders/process          — atomic: create OT + mark reception FINISHED
GET    /work-orders/{id}/lines       — list lines
POST   /work-orders/{id}/lines       — add a line
DELETE /work-orders/{id}/lines/{lid} — remove a line
"""
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.reception import Reception, ReceptionStatus
from app.models.reception_detail import ReceptionDetail
from app.models.work_order import (
    WORK_ORDER_TRANSITIONS,
    WorkOrder,
    WorkOrderLine,
    WorkOrderStatus,
)
from app.schemas.work_order import (
    LaborItemCreate,
    ProcessWorkOrderInput,
    ProcessWorkOrderResult,
    WorkOrderCreate,
    WorkOrderLineCreate,
    WorkOrderLineResponse,
    WorkOrderList,
    WorkOrderResponse,
    WorkOrderUpdate,
)

router = APIRouter(prefix="/work-orders", tags=["Work Orders"])

_CENT = Decimal("0.01")
_ORDER_NUMBER_BASE = 1001


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _subtotal(
    quantity: Decimal,
    unit_price: Decimal,
    discount_percentage: Decimal = Decimal("0.00"),
) -> Decimal:
    """Net line subtotal after optional percentage discount, rounded to 2dp.

    Formula: quantity * unit_price * (1 - discount_percentage / 100)
    """
    factor = Decimal("1") - (discount_percentage / Decimal("100"))
    return (quantity * unit_price * factor).quantize(_CENT, rounding=ROUND_HALF_UP)


def _assert_transition(current: WorkOrderStatus, requested: WorkOrderStatus) -> None:
    allowed = WORK_ORDER_TRANSITIONS[current]
    if requested not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot transition from '{current.value}' to '{requested.value}'. "
                f"Allowed: {[s.value for s in allowed] or 'none (terminal state)'}"
            ),
        )


def _compute_totals(
    lines: list[WorkOrderLine],
    tax_rate: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Return (total_labor, total_parts, tax_amount, total_final)."""
    labor = sum((ln.subtotal for ln in lines if not ln.is_part), Decimal("0.00"))
    parts = sum((ln.subtotal for ln in lines if ln.is_part), Decimal("0.00"))
    tax   = ((labor + parts) * tax_rate).quantize(_CENT, rounding=ROUND_HALF_UP)
    final = labor + parts + tax
    return labor, parts, tax, final


async def _next_order_number(db: AsyncSession) -> str:
    n = await db.scalar(select(func.count()).select_from(WorkOrder))
    return f"OT-{(n or 0) + _ORDER_NUMBER_BASE}"


# ---------------------------------------------------------------------------
# Work Order CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=WorkOrderList)
async def list_work_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    reception_id: UUID | None = Query(None),
    status_filter: WorkOrderStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    q = select(WorkOrder)
    cq = select(func.count()).select_from(WorkOrder)

    filters = []
    if reception_id is not None:
        filters.append(WorkOrder.reception_id == reception_id)
    if status_filter is not None:
        filters.append(WorkOrder.status == status_filter)

    for f in filters:
        q  = q.where(f)
        cq = cq.where(f)

    total = await db.scalar(cq)
    result = await db.execute(q.order_by(WorkOrder.created_at.desc()).offset(skip).limit(limit))
    return WorkOrderList(total=total or 0, items=list(result.scalars().all()))


@router.get("/{work_order_id}", response_model=WorkOrderResponse)
async def get_work_order(work_order_id: UUID, db: AsyncSession = Depends(get_db)):
    wo = await db.get(WorkOrder, work_order_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    return wo


@router.post("", response_model=WorkOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_work_order(payload: WorkOrderCreate, db: AsyncSession = Depends(get_db)):
    reception = await db.get(Reception, payload.reception_id)
    if not reception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reception {payload.reception_id} not found",
        )

    wo = WorkOrder(
        reception_id=payload.reception_id,
        currency_id=payload.currency_id,
        notes=payload.notes,
        order_number=await _next_order_number(db),
    )
    db.add(wo)
    await db.flush()

    built_lines: list[WorkOrderLine] = []
    for ln in payload.lines:
        line = WorkOrderLine(
            work_order_id=wo.id,
            reception_detail_id=ln.reception_detail_id,
            description=ln.description,
            quantity=ln.quantity,
            unit_price=ln.unit_price,
            is_part=ln.is_part,
            discount_percentage=ln.discount_percentage,
            subtotal=_subtotal(ln.quantity, ln.unit_price, ln.discount_percentage),
        )
        db.add(line)
        built_lines.append(line)

    wo.total_labor, wo.total_parts, wo.tax_amount, wo.total_final = _compute_totals(built_lines)
    await db.flush()
    await db.refresh(wo)
    return wo


@router.patch("/{work_order_id}", response_model=WorkOrderResponse)
async def update_work_order(
    work_order_id: UUID,
    payload: WorkOrderUpdate,
    db: AsyncSession = Depends(get_db),
):
    wo = await db.get(WorkOrder, work_order_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")

    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates:
        _assert_transition(wo.status, updates["status"])

    for field, value in updates.items():
        setattr(wo, field, value)

    await db.flush()
    await db.refresh(wo)
    return wo


@router.delete("/{work_order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_order(work_order_id: UUID, db: AsyncSession = Depends(get_db)):
    wo = await db.get(WorkOrder, work_order_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    if wo.status not in (WorkOrderStatus.DRAFT, WorkOrderStatus.CANCELLED):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot delete a work order in status '{wo.status.value}'.",
        )
    await db.delete(wo)


@router.patch("/{work_order_id}/status", response_model=WorkOrderResponse)
async def transition_work_order_status(
    work_order_id: UUID,
    requested: WorkOrderStatus,
    db: AsyncSession = Depends(get_db),
):
    """Apply a lifecycle transition (replaces the old /close endpoint)."""
    wo = await db.get(WorkOrder, work_order_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    _assert_transition(wo.status, requested)
    wo.status = requested
    await db.flush()
    await db.refresh(wo)
    return wo


@router.patch("/{work_order_id}/cancel", response_model=WorkOrderResponse)
async def cancel_work_order(
    work_order_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a WorkOrder and atomically revert the linked Reception to IN_PROGRESS.

    Business rules:
    - The work order must allow a transition to CANCELLED (any non-terminal state).
    - The linked Reception is set back to IN_PROGRESS so mechanics can continue working.
    """
    wo = await db.get(WorkOrder, work_order_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")

    _assert_transition(wo.status, WorkOrderStatus.CANCELLED)

    reception = await db.get(Reception, wo.reception_id)
    if not reception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Linked reception {wo.reception_id} not found",
        )

    wo.status = WorkOrderStatus.CANCELLED
    reception.current_status = ReceptionStatus.IN_PROGRESS
    await db.flush()
    await db.refresh(wo)
    return wo


# ---------------------------------------------------------------------------
# Process (atomic creation from reception details)
# ---------------------------------------------------------------------------

@router.post(
    "/process",
    response_model=ProcessWorkOrderResult,
    status_code=status.HTTP_201_CREATED,
)
async def process_work_order(
    payload: ProcessWorkOrderInput,
    db: AsyncSession = Depends(get_db),
):
    """Create a WorkOrder atomically from a Reception.

    Steps:
    1. Verify Reception exists.
    2. Load each ReceptionDetail for labor_items — must belong to the same Reception.
    3. Verify no detail is already linked to an active (non-CANCELLED) WorkOrderLine.
    4. Auto-generate order_number.
    5. Create WorkOrder + WorkOrderLines:
         a. Labour lines: one per labor_item, description from ReceptionDetail,
            pricing (quantity / unit_price / discount) from the request.
         b. Extra lines: parts, fees, etc. supplied directly by the caller.
    6. Compute and store totals (labor, parts, tax, final).
    """
    # 1. Reception exists + business-rule guard
    reception = await db.get(Reception, payload.reception_id)
    if not reception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reception {payload.reception_id} not found",
        )
    if reception.current_status not in (ReceptionStatus.NEW, ReceptionStatus.IN_PROGRESS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot create a work order for a reception in status "
                f"'{reception.current_status.value}'. "
                "Reception must be NEW or IN_PROGRESS."
            ),
        )

    # 2. Load and validate ReceptionDetail rows for each labor_item
    detail_map: dict[UUID, ReceptionDetail] = {}
    for item in payload.labor_items:
        rid = item.reception_detail_id
        if rid in detail_map:
            continue  # already loaded (de-duplicate)
        detail = await db.get(ReceptionDetail, rid)
        if not detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ReceptionDetail {rid} not found",
            )
        if detail.reception_id != payload.reception_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"ReceptionDetail {rid} does not belong to reception {payload.reception_id}",
            )
        detail_map[rid] = detail

    # 3. Check for conflicts with active work orders
    labor_detail_ids = list(detail_map.keys())
    if labor_detail_ids:
        conflict = await db.scalar(
            select(func.count())
            .select_from(WorkOrderLine)
            .join(WorkOrder, WorkOrder.id == WorkOrderLine.work_order_id)
            .where(
                WorkOrderLine.reception_detail_id.in_(labor_detail_ids),
                WorkOrder.status != WorkOrderStatus.CANCELLED,
            )
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="One or more ReceptionDetail rows are already invoiced in an active work order.",
            )

    # 4. Order number
    order_number = await _next_order_number(db)

    # 5. Create WorkOrder header
    wo = WorkOrder(
        reception_id=payload.reception_id,
        currency_id=payload.currency_id,
        notes=payload.notes,
        order_number=order_number,
    )
    db.add(wo)
    await db.flush()

    built_lines: list[WorkOrderLine] = []

    # 5a. Labour lines — description from ReceptionDetail, pricing from request
    for item in payload.labor_items:
        detail = detail_map[item.reception_detail_id]
        sub = _subtotal(item.quantity, item.unit_price, item.discount_percentage)
        line = WorkOrderLine(
            work_order_id=wo.id,
            reception_detail_id=item.reception_detail_id,
            description=detail.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            is_part=False,
            discount_percentage=item.discount_percentage,
            subtotal=sub,
        )
        db.add(line)
        built_lines.append(line)

    # 5b. Extra lines (parts, fees, etc.)
    for ln in payload.extra_lines:
        sub = _subtotal(ln.quantity, ln.unit_price, ln.discount_percentage)
        line = WorkOrderLine(
            work_order_id=wo.id,
            reception_detail_id=ln.reception_detail_id,
            description=ln.description,
            quantity=ln.quantity,
            unit_price=ln.unit_price,
            is_part=ln.is_part,
            discount_percentage=ln.discount_percentage,
            subtotal=sub,
        )
        db.add(line)
        built_lines.append(line)

    # 6. Compute and persist totals; mark reception as FINISHED
    wo.total_labor, wo.total_parts, wo.tax_amount, wo.total_final = _compute_totals(
        built_lines, payload.tax_rate
    )
    reception.current_status = ReceptionStatus.FINISHED
    await db.flush()

    return ProcessWorkOrderResult(
        work_order_id=wo.id,
        order_number=wo.order_number,
        lines_created=len(built_lines),
        total_labor=wo.total_labor,
        total_parts=wo.total_parts,
        tax_amount=wo.tax_amount,
        total_final=wo.total_final,
        reception_status=reception.current_status,
    )


# ---------------------------------------------------------------------------
# WorkOrderLine sub-resource
# ---------------------------------------------------------------------------

@router.get(
    "/{work_order_id}/lines",
    response_model=list[WorkOrderLineResponse],
    tags=["Work Order Lines"],
)
async def list_lines(work_order_id: UUID, db: AsyncSession = Depends(get_db)):
    wo = await db.get(WorkOrder, work_order_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    result = await db.execute(
        select(WorkOrderLine).where(WorkOrderLine.work_order_id == work_order_id)
    )
    return list(result.scalars().all())


@router.post(
    "/{work_order_id}/lines",
    response_model=WorkOrderLineResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Work Order Lines"],
)
async def add_line(
    work_order_id: UUID,
    payload: WorkOrderLineCreate,
    db: AsyncSession = Depends(get_db),
):
    wo = await db.get(WorkOrder, work_order_id)
    if not wo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    if wo.status not in (WorkOrderStatus.DRAFT, WorkOrderStatus.SENT):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot add lines to a work order in status '{wo.status.value}'.",
        )

    sub = _subtotal(payload.quantity, payload.unit_price, payload.discount_percentage)
    line = WorkOrderLine(
        work_order_id=work_order_id,
        reception_detail_id=payload.reception_detail_id,
        description=payload.description,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        is_part=payload.is_part,
        discount_percentage=payload.discount_percentage,
        subtotal=sub,
    )
    db.add(line)
    await db.flush()

    # Recompute totals on the parent
    all_lines_result = await db.execute(
        select(WorkOrderLine).where(WorkOrderLine.work_order_id == work_order_id)
    )
    wo.total_labor, wo.total_parts, wo.tax_amount, wo.total_final = _compute_totals(
        list(all_lines_result.scalars().all())
    )
    await db.flush()
    await db.refresh(line)
    return line


@router.delete(
    "/{work_order_id}/lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Work Order Lines"],
)
async def delete_line(
    work_order_id: UUID,
    line_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    line = await db.get(WorkOrderLine, line_id)
    if not line or line.work_order_id != work_order_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line not found")
    await db.delete(line)

    wo = await db.get(WorkOrder, work_order_id)
    if wo:
        all_lines_result = await db.execute(
            select(WorkOrderLine).where(WorkOrderLine.work_order_id == work_order_id)
        )
        wo.total_labor, wo.total_parts, wo.tax_amount, wo.total_final = _compute_totals(
            list(all_lines_result.scalars().all())
        )
        await db.flush()

