"""Add timezone column to capsules table

Revision ID: 001_add_timezone
Revises: 
Create Date: 2026-03-25

This migration adds the timezone column to the capsules table to support
timezone-aware unlock dates. Existing capsules will default to 'UTC'.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_add_timezone'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add timezone column with default 'UTC' for existing records
    op.add_column(
        'capsules',
        sa.Column('timezone', sa.String(64), nullable=False, server_default='UTC')
    )
    
    # Create index for timezone column
    op.create_index('idx_capsules_timezone', 'capsules', ['timezone'])


def downgrade() -> None:
    # Remove index first
    op.drop_index('idx_capsules_timezone', table_name='capsules')
    
    # Remove timezone column
    op.drop_column('capsules', 'timezone')
