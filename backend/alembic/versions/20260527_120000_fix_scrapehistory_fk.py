"""Add FK constraint on scrape_history.config_id and cascade deletes

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-05-27 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6g7h8i9'
down_revision = 'c3d4e5f6g7h8'
branch_labels = None
depends_on = None


def upgrade():
    # Remove orphaned history rows (configs that no longer exist) before adding the constraint
    op.execute(
        "DELETE FROM scrape_history WHERE config_id NOT IN (SELECT id FROM scrape_configs)"
    )

    op.create_foreign_key(
        'fk_scrape_history_config_id',
        'scrape_history',
        'scrape_configs',
        ['config_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade():
    op.drop_constraint('fk_scrape_history_config_id', 'scrape_history', type_='foreignkey')
