"""Add market_indicators and market_events tables

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-10-07 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6g7h8i9j0'
down_revision = 'd4e5f6g7h8i9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'market_indicators',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('series_key', sa.String(100), nullable=False),
        sa.Column('obs_date', sa.Date(), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(32), nullable=True),
        sa.Column('source', sa.String(64), nullable=True),
        sa.Column('label', sa.String(255), nullable=True),
        sa.Column('scraped_at', sa.DateTime(), nullable=True),
        sa.Column('snapshot_id', sa.String(255), nullable=True),
        sa.UniqueConstraint('series_key', 'obs_date', name='uq_market_indicator_series_date'),
    )
    op.create_index('ix_market_indicators_id', 'market_indicators', ['id'])
    op.create_index('ix_market_indicators_series_key', 'market_indicators', ['series_key'])
    op.create_index('ix_market_indicators_obs_date', 'market_indicators', ['obs_date'])
    op.create_index('ix_market_indicators_snapshot_id', 'market_indicators', ['snapshot_id'])

    op.create_table(
        'market_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('category', sa.String(64), nullable=True),
        sa.Column('direction', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('magnitude', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('horizon', sa.String(16), nullable=False, server_default='all'),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('expires_on', sa.Date(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_market_events_id', 'market_events', ['id'])


def downgrade():
    op.drop_table('market_events')
    op.drop_table('market_indicators')
