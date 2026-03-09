"""redesign_work_orders

Revision ID: 35310d98cb8b
Revises: 93b485ca5c53
Create Date: 2026-03-08 19:10:11.288912

Manual curation notes
---------------------
* `work_order_status` ENUM must be created in PostgreSQL BEFORE the status
  column is retyped — autogenerate alone cannot do this safely.
* The status column has an incompatible string value set, so we:
    1. DROP DEFAULT on status
    2. UPDATE existing rows to 'DRAFT' (safe on empty table, correct on legacy)
    3. ALTER TYPE … USING text cast
    4. SET DEFAULT 'DRAFT'
    5. DROP old `order_status` type
* `reception_id` and `order_number` are NOT NULL — safe only on an empty table;
  for non-empty tables a back-fill script would be needed first.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '35310d98cb8b'
down_revision: Union[str, None] = '93b485ca5c53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 0. Create new ENUM type before any column references it ───────────────
    op.execute(
        "CREATE TYPE work_order_status AS ENUM "
        "('DRAFT', 'SENT', 'APPROVED', 'INVOICED', 'CANCELLED')"
    )

    # ── 1. New table: work_order_lines ────────────────────────────────────────
    op.create_table(
        'work_order_lines',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('work_order_id', sa.UUID(), nullable=False),
        sa.Column('reception_detail_id', sa.UUID(), nullable=True),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('is_part', sa.Boolean(), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ['reception_detail_id'], ['reception_details.id'],
            name='fk_work_order_lines_reception_detail_id', ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['work_order_id'], ['work_orders.id'],
            name='fk_work_order_lines_work_order_id', ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_work_order_lines_reception_detail_id'),
        'work_order_lines', ['reception_detail_id'], unique=False,
    )
    op.create_index(
        op.f('ix_work_order_lines_work_order_id'),
        'work_order_lines', ['work_order_id'], unique=False,
    )

    # ── 2. Drop old table: work_order_items ───────────────────────────────────
    op.drop_index('ix_work_order_items_currency_id', table_name='work_order_items')
    op.drop_index('ix_work_order_items_work_order_id', table_name='work_order_items')
    op.drop_table('work_order_items')

    # ── 3. Add new columns to work_orders (nullable where safe) ───────────────
    op.add_column('work_orders', sa.Column('reception_id', sa.UUID(), nullable=False))
    op.add_column('work_orders', sa.Column('currency_id', sa.UUID(), nullable=True))
    op.add_column('work_orders', sa.Column('order_number', sa.String(length=20), nullable=False))
    op.add_column('work_orders', sa.Column(
        'total_labor', sa.Numeric(precision=12, scale=2),
        server_default='0.00', nullable=False,
    ))
    op.add_column('work_orders', sa.Column(
        'total_parts', sa.Numeric(precision=12, scale=2),
        server_default='0.00', nullable=False,
    ))
    op.add_column('work_orders', sa.Column(
        'tax_amount', sa.Numeric(precision=12, scale=2),
        server_default='0.00', nullable=False,
    ))
    op.add_column('work_orders', sa.Column(
        'total_final', sa.Numeric(precision=12, scale=2),
        server_default='0.00', nullable=False,
    ))
    op.add_column('work_orders', sa.Column(
        'updated_at', sa.DateTime(timezone=True),
        server_default=sa.text('now()'), nullable=False,
    ))

    # ── 4. Retype status column (ENUM migration) ──────────────────────────────
    # Step through text so the UPDATE can use the new literal 'DRAFT'
    op.execute("ALTER TABLE work_orders ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE work_orders ALTER COLUMN status "
        "TYPE text USING status::text"
    )
    op.execute("UPDATE work_orders SET status = 'DRAFT'")
    op.execute(
        "ALTER TABLE work_orders ALTER COLUMN status "
        "TYPE work_order_status USING status::work_order_status"
    )
    op.execute("ALTER TABLE work_orders ALTER COLUMN status SET DEFAULT 'DRAFT'")

    # ── 5. Drop old ENUM type ─────────────────────────────────────────────────
    op.execute("DROP TYPE order_status")

    # ── 6. Index changes ──────────────────────────────────────────────────────
    op.drop_index('ix_work_orders_vehicle_id', table_name='work_orders')
    op.drop_index('ix_work_orders_vehicle_id_created_at', table_name='work_orders')
    op.create_index(op.f('ix_work_orders_currency_id'), 'work_orders', ['currency_id'], unique=False)
    op.create_index(op.f('ix_work_orders_order_number'), 'work_orders', ['order_number'], unique=True)
    op.create_index('ix_work_orders_reception_id', 'work_orders', ['reception_id'], unique=False)

    # ── 7. Foreign key changes ────────────────────────────────────────────────
    op.drop_constraint('fk_work_orders_vehicle_id', 'work_orders', type_='foreignkey')
    op.create_foreign_key(
        'fk_work_orders_currency_id', 'work_orders', 'currencies',
        ['currency_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_work_orders_reception_id', 'work_orders', 'receptions',
        ['reception_id'], ['id'], ondelete='RESTRICT',
    )

    # ── 8. Drop obsolete columns ──────────────────────────────────────────────
    op.drop_column('work_orders', 'closed_at')
    op.drop_column('work_orders', 'vehicle_id')
    op.drop_column('work_orders', 'checkin_photos')


def downgrade() -> None:
    # ── 0. Re-create old ENUM type ────────────────────────────────────────────
    op.execute(
        "CREATE TYPE order_status AS ENUM ('received', 'in_progress', 'delivered')"
    )

    # ── 1. Restore obsolete columns ───────────────────────────────────────────
    op.add_column('work_orders', sa.Column(
        'checkin_photos', postgresql.JSON(astext_type=sa.Text()),
        autoincrement=False, nullable=True,
    ))
    op.add_column('work_orders', sa.Column(
        'vehicle_id', sa.UUID(), autoincrement=False, nullable=True,  # nullable for back-fill
    ))
    op.add_column('work_orders', sa.Column(
        'closed_at', postgresql.TIMESTAMP(timezone=True),
        autoincrement=False, nullable=True,
    ))

    # ── 2. Restore foreign keys ───────────────────────────────────────────────
    op.drop_constraint('fk_work_orders_reception_id', 'work_orders', type_='foreignkey')
    op.drop_constraint('fk_work_orders_currency_id', 'work_orders', type_='foreignkey')
    op.create_foreign_key(
        'fk_work_orders_vehicle_id', 'work_orders', 'vehicles',
        ['vehicle_id'], ['id'], ondelete='RESTRICT',
    )

    # ── 3. Restore index set ──────────────────────────────────────────────────
    op.drop_index('ix_work_orders_reception_id', table_name='work_orders')
    op.drop_index(op.f('ix_work_orders_order_number'), table_name='work_orders')
    op.drop_index(op.f('ix_work_orders_currency_id'), table_name='work_orders')
    op.create_index(
        'ix_work_orders_vehicle_id_created_at', 'work_orders',
        ['vehicle_id', 'created_at'], unique=False,
    )
    op.create_index('ix_work_orders_vehicle_id', 'work_orders', ['vehicle_id'], unique=False)

    # ── 4. Retype status column back to order_status ──────────────────────────
    op.execute("ALTER TABLE work_orders ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE work_orders ALTER COLUMN status "
        "TYPE text USING status::text"
    )
    op.execute("UPDATE work_orders SET status = 'received'")
    op.execute(
        "ALTER TABLE work_orders ALTER COLUMN status "
        "TYPE order_status USING status::order_status"
    )

    # ── 5. Drop new ENUM type ─────────────────────────────────────────────────
    op.execute("DROP TYPE work_order_status")

    # ── 6. Remove new columns ─────────────────────────────────────────────────
    op.drop_column('work_orders', 'updated_at')
    op.drop_column('work_orders', 'total_final')
    op.drop_column('work_orders', 'tax_amount')
    op.drop_column('work_orders', 'total_parts')
    op.drop_column('work_orders', 'total_labor')
    op.drop_column('work_orders', 'order_number')
    op.drop_column('work_orders', 'currency_id')
    op.drop_column('work_orders', 'reception_id')

    # ── 7. Restore work_order_items table ─────────────────────────────────────
    op.create_table(
        'work_order_items',
        sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('work_order_id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('description', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
        sa.Column('quantity', sa.NUMERIC(precision=10, scale=3), autoincrement=False, nullable=False),
        sa.Column('unit_price', sa.NUMERIC(precision=10, scale=2), autoincrement=False, nullable=False),
        sa.Column('total', sa.NUMERIC(precision=10, scale=2), autoincrement=False, nullable=False),
        sa.Column('currency_id', sa.UUID(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(
            ['currency_id'], ['currencies.id'],
            name='work_order_items_currency_id_fkey', ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['work_order_id'], ['work_orders.id'],
            name='fk_work_order_items_work_order_id', ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name='work_order_items_pkey'),
    )
    op.create_index(
        'ix_work_order_items_work_order_id',
        'work_order_items', ['work_order_id'], unique=False,
    )
    op.create_index(
        'ix_work_order_items_currency_id',
        'work_order_items', ['currency_id'], unique=False,
    )

    # ── 8. Drop work_order_lines table ────────────────────────────────────────
    op.drop_index(op.f('ix_work_order_lines_work_order_id'), table_name='work_order_lines')
    op.drop_index(op.f('ix_work_order_lines_reception_detail_id'), table_name='work_order_lines')
    op.drop_table('work_order_lines')

