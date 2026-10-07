"""add scraped_data and snapshot_id to scrape_history

Revision ID: c3d4e5f6g7h8
Revises: b1a2c3d4e5f6
Create Date: 2026-01-22 10:55:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6g7h8'
down_revision = 'b1a2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Add scraped_data JSON column to store summary of scraped records
    op.add_column('scrape_history', sa.Column('scraped_data', sa.JSON(), nullable=True))
    
    # Add snapshot_id to link to oil_prices records
    op.add_column('scrape_history', sa.Column('snapshot_id', sa.String(36), nullable=True))
    
    # Create index for snapshot_id lookups
    op.create_index(op.f('ix_scrape_history_snapshot_id'), 'scrape_history', ['snapshot_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_scrape_history_snapshot_id'), table_name='scrape_history')
    op.drop_column('scrape_history', 'snapshot_id')
    op.drop_column('scrape_history', 'scraped_data')
