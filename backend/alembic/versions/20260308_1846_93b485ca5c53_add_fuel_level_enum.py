"""add_fuel_level_enum

Revision ID: 93b485ca5c53
Revises: 6c2dc318a980
Create Date: 2026-03-08 18:46:51.281082

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93b485ca5c53'
down_revision: Union[str, None] = '6c2dc318a980'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create the PostgreSQL ENUM type first — op.alter_column cannot do this implicitly.
    op.execute(sa.text(
        "CREATE TYPE fuel_level AS ENUM ('EMPTY', 'QUARTER', 'HALF', 'THREE_QUARTERS', 'FULL')"
    ))
    # 2. Nullify any existing free-text values (e.g. '3/4', 'Full') that cannot be
    #    cast to the new enum — this is safe in development; add a data-mapping
    #    UPDATE here if you need to preserve existing rows in production.
    op.execute(sa.text("UPDATE receptions SET fuel_level = NULL"))
    # 3. Change the column type — NULL::fuel_level casts cleanly.
    op.execute(sa.text(
        "ALTER TABLE receptions ALTER COLUMN fuel_level TYPE fuel_level "
        "USING fuel_level::fuel_level"
    ))


def downgrade() -> None:
    # Reverse: cast enum back to plain text, then drop the type.
    op.execute(sa.text(
        "ALTER TABLE receptions ALTER COLUMN fuel_level TYPE VARCHAR(20) "
        "USING fuel_level::varchar"
    ))
    op.execute(sa.text("DROP TYPE fuel_level"))
