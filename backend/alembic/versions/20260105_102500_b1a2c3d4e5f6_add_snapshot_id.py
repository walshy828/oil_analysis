"""add snapshot_id to oil_prices

Revision ID: b1a2c3d4e5f6
Revises: a0357ddad2b7
Create Date: 2026-01-05 10:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1a2c3d4e5f6'
down_revision: Union[str, None] = 'a0357ddad2b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('oil_prices', sa.Column('snapshot_id', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_oil_prices_snapshot_id'), 'oil_prices', ['snapshot_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_oil_prices_snapshot_id'), table_name='oil_prices')
    op.drop_column('oil_prices', 'snapshot_id')
