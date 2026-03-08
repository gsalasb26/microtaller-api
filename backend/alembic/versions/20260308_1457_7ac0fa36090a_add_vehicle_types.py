"""add_vehicle_types

Revision ID: 7ac0fa36090a
Revises:
Create Date: 2026-03-08 14:57:13.139078

Manually curated:
  - ENUM created via raw SQL before any column references it.
  - DEFAULT dropped before ALTER COLUMN to avoid cast error, then restored.
  - Explicit FK names so downgrade can drop them by name.
  - server_default on PK/id columns removed (autogenerate noise).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7ac0fa36090a'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Create the order_status ENUM type before any column references it ──
    # The tables were originally created via raw SQL (not Alembic), so the type
    # may not exist yet.  IF NOT EXISTS requires PG ≥ 9.1 (always true here).
    op.execute(sa.text(
        "CREATE TYPE order_status AS ENUM ('received', 'in_progress', 'delivered')"
    ))

    # ── 2. New table: vehicle_types ───────────────────────────────────────────
    op.create_table(
        'vehicle_types',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_vehicle_types_name'), 'vehicle_types', ['name'], unique=True)

    # ── 3. customers — tighten column types & add index ───────────────────────
    op.alter_column('customers', 'name',
                    existing_type=sa.VARCHAR(length=150),
                    type_=sa.String(length=100),
                    existing_nullable=False)
    op.alter_column('customers', 'phone',
                    existing_type=sa.VARCHAR(length=50),
                    type_=sa.String(length=20),
                    nullable=False)
    op.alter_column('customers', 'created_at',
                    existing_type=postgresql.TIMESTAMP(),
                    type_=sa.DateTime(timezone=True),
                    nullable=False,
                    existing_server_default=sa.text('now()'))
    op.create_index(op.f('ix_customers_name'), 'customers', ['name'], unique=False)

    # ── 4. vehicles — new column, tighten types, recreate FKs with ON DELETE ──
    op.add_column('vehicles', sa.Column('vehicle_type_id', sa.UUID(), nullable=True))
    op.alter_column('vehicles', 'brand',
                    existing_type=sa.VARCHAR(length=50),
                    type_=sa.String(length=80),
                    nullable=False)
    op.alter_column('vehicles', 'model',
                    existing_type=sa.VARCHAR(length=50),
                    type_=sa.String(length=80),
                    nullable=False)
    op.alter_column('vehicles', 'year',
                    existing_type=sa.INTEGER(),
                    nullable=False)
    op.alter_column('vehicles', 'created_at',
                    existing_type=postgresql.TIMESTAMP(),
                    type_=sa.DateTime(timezone=True),
                    nullable=False,
                    existing_server_default=sa.text('now()'))
    op.create_index(op.f('ix_vehicles_customer_id'), 'vehicles', ['customer_id'], unique=False)
    op.create_index(op.f('ix_vehicles_plate'), 'vehicles', ['plate'], unique=True)
    op.create_index(op.f('ix_vehicles_vehicle_type_id'), 'vehicles', ['vehicle_type_id'], unique=False)
    op.drop_constraint('vehicles_customer_id_fkey', 'vehicles', type_='foreignkey')
    op.create_foreign_key(
        'fk_vehicles_customer_id', 'vehicles', 'customers',
        ['customer_id'], ['id'], ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'fk_vehicles_vehicle_type_id', 'vehicles', 'vehicle_types',
        ['vehicle_type_id'], ['id'], ondelete='SET NULL',
    )

    # ── 5. work_order_items — tighten numeric precision & recreate FK ─────────
    op.alter_column('work_order_items', 'quantity',
                    existing_type=sa.NUMERIC(precision=10, scale=2),
                    type_=sa.Numeric(precision=10, scale=3),
                    existing_nullable=False)
    op.alter_column('work_order_items', 'unit_price',
                    existing_type=sa.NUMERIC(precision=12, scale=2),
                    type_=sa.Numeric(precision=10, scale=2),
                    existing_nullable=False)
    op.alter_column('work_order_items', 'total',
                    existing_type=sa.NUMERIC(precision=12, scale=2),
                    type_=sa.Numeric(precision=10, scale=2),
                    existing_nullable=False)
    op.create_index(
        op.f('ix_work_order_items_work_order_id'),
        'work_order_items', ['work_order_id'], unique=False,
    )
    op.drop_constraint('work_order_items_work_order_id_fkey', 'work_order_items', type_='foreignkey')
    op.create_foreign_key(
        'fk_work_order_items_work_order_id', 'work_order_items', 'work_orders',
        ['work_order_id'], ['id'], ondelete='CASCADE',
    )

    # ── 6. work_orders — cast status VARCHAR → ENUM, add indexes, recreate FK ─
    # Step 1: drop the existing DEFAULT so PG can change the column type freely.
    # Step 2: cast all existing rows using USING clause.
    # Step 3: restore the default with the ENUM literal.
    op.execute(sa.text(
        "ALTER TABLE work_orders ALTER COLUMN status DROP DEFAULT"
    ))
    op.execute(sa.text(
        "ALTER TABLE work_orders ALTER COLUMN status "
        "TYPE order_status USING status::order_status"
    ))
    op.execute(sa.text(
        "ALTER TABLE work_orders ALTER COLUMN status SET DEFAULT 'received'"
    ))
    op.alter_column('work_orders', 'checkin_photos',
                    existing_type=postgresql.JSONB(astext_type=sa.Text()),
                    type_=sa.JSON(),
                    existing_nullable=True)
    op.alter_column('work_orders', 'created_at',
                    existing_type=postgresql.TIMESTAMP(),
                    type_=sa.DateTime(timezone=True),
                    nullable=False,
                    existing_server_default=sa.text('now()'))
    op.alter_column('work_orders', 'closed_at',
                    existing_type=postgresql.TIMESTAMP(),
                    type_=sa.DateTime(timezone=True),
                    existing_nullable=True)
    op.create_index(op.f('ix_work_orders_status'), 'work_orders', ['status'], unique=False)
    op.create_index('ix_work_orders_status_created_at', 'work_orders', ['status', 'created_at'], unique=False)
    op.create_index(op.f('ix_work_orders_vehicle_id'), 'work_orders', ['vehicle_id'], unique=False)
    op.create_index('ix_work_orders_vehicle_id_created_at', 'work_orders', ['vehicle_id', 'created_at'], unique=False)
    op.drop_constraint('work_orders_vehicle_id_fkey', 'work_orders', type_='foreignkey')
    op.create_foreign_key(
        'fk_work_orders_vehicle_id', 'work_orders', 'vehicles',
        ['vehicle_id'], ['id'], ondelete='RESTRICT',
    )


def downgrade() -> None:
    # ── work_orders ───────────────────────────────────────────────────────────
    op.drop_constraint('fk_work_orders_vehicle_id', 'work_orders', type_='foreignkey')
    op.create_foreign_key('work_orders_vehicle_id_fkey', 'work_orders', 'vehicles', ['vehicle_id'], ['id'])
    op.drop_index('ix_work_orders_vehicle_id_created_at', table_name='work_orders')
    op.drop_index(op.f('ix_work_orders_vehicle_id'), table_name='work_orders')
    op.drop_index('ix_work_orders_status_created_at', table_name='work_orders')
    op.drop_index(op.f('ix_work_orders_status'), table_name='work_orders')
    op.alter_column('work_orders', 'closed_at',
                    existing_type=sa.DateTime(timezone=True),
                    type_=postgresql.TIMESTAMP(),
                    existing_nullable=True)
    op.alter_column('work_orders', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    type_=postgresql.TIMESTAMP(),
                    nullable=True,
                    existing_server_default=sa.text('now()'))
    op.alter_column('work_orders', 'checkin_photos',
                    existing_type=sa.JSON(),
                    type_=postgresql.JSONB(astext_type=sa.Text()),
                    existing_nullable=True)
    # Reverse: DROP DEFAULT → cast back to VARCHAR → restore original default
    op.execute(sa.text(
        "ALTER TABLE work_orders ALTER COLUMN status DROP DEFAULT"
    ))
    op.execute(sa.text(
        "ALTER TABLE work_orders ALTER COLUMN status "
        "TYPE VARCHAR(20) USING status::varchar"
    ))
    op.execute(sa.text(
        "ALTER TABLE work_orders ALTER COLUMN status SET DEFAULT 'received'"
    ))
    # Drop the ENUM type only after no column references it
    op.execute(sa.text('DROP TYPE order_status'))

    # ── work_order_items ──────────────────────────────────────────────────────
    op.drop_constraint('fk_work_order_items_work_order_id', 'work_order_items', type_='foreignkey')
    op.create_foreign_key('work_order_items_work_order_id_fkey', 'work_order_items', 'work_orders', ['work_order_id'], ['id'])
    op.drop_index(op.f('ix_work_order_items_work_order_id'), table_name='work_order_items')
    op.alter_column('work_order_items', 'total',
                    existing_type=sa.Numeric(precision=10, scale=2),
                    type_=sa.NUMERIC(precision=12, scale=2),
                    existing_nullable=False)
    op.alter_column('work_order_items', 'unit_price',
                    existing_type=sa.Numeric(precision=10, scale=2),
                    type_=sa.NUMERIC(precision=12, scale=2),
                    existing_nullable=False)
    op.alter_column('work_order_items', 'quantity',
                    existing_type=sa.Numeric(precision=10, scale=3),
                    type_=sa.NUMERIC(precision=10, scale=2),
                    existing_nullable=False)

    # ── vehicles ──────────────────────────────────────────────────────────────
    op.drop_constraint('fk_vehicles_vehicle_type_id', 'vehicles', type_='foreignkey')
    op.drop_constraint('fk_vehicles_customer_id', 'vehicles', type_='foreignkey')
    op.create_foreign_key('vehicles_customer_id_fkey', 'vehicles', 'customers', ['customer_id'], ['id'])
    op.drop_index(op.f('ix_vehicles_vehicle_type_id'), table_name='vehicles')
    op.drop_index(op.f('ix_vehicles_plate'), table_name='vehicles')
    op.drop_index(op.f('ix_vehicles_customer_id'), table_name='vehicles')
    op.alter_column('vehicles', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    type_=postgresql.TIMESTAMP(),
                    nullable=True,
                    existing_server_default=sa.text('now()'))
    op.alter_column('vehicles', 'year',
                    existing_type=sa.INTEGER(),
                    nullable=True)
    op.alter_column('vehicles', 'model',
                    existing_type=sa.String(length=80),
                    type_=sa.VARCHAR(length=50),
                    nullable=True)
    op.alter_column('vehicles', 'brand',
                    existing_type=sa.String(length=80),
                    type_=sa.VARCHAR(length=50),
                    nullable=True)
    op.drop_column('vehicles', 'vehicle_type_id')

    # ── customers ─────────────────────────────────────────────────────────────
    op.drop_index(op.f('ix_customers_name'), table_name='customers')
    op.alter_column('customers', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    type_=postgresql.TIMESTAMP(),
                    nullable=True,
                    existing_server_default=sa.text('now()'))
    op.alter_column('customers', 'phone',
                    existing_type=sa.String(length=20),
                    type_=sa.VARCHAR(length=50),
                    nullable=True)
    op.alter_column('customers', 'name',
                    existing_type=sa.String(length=100),
                    type_=sa.VARCHAR(length=150),
                    existing_nullable=False)

    # ── vehicle_types ─────────────────────────────────────────────────────────
    op.drop_index(op.f('ix_vehicle_types_name'), table_name='vehicle_types')
    op.drop_table('vehicle_types')
    # ### end Alembic commands ###
