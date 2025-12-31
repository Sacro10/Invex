"""add_billing_update_retry_table

Revision ID: 0fe3741913fa
Revises: ffbdfeebd16c
Create Date: 2025-12-31 13:16:22.165759

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0fe3741913fa'
down_revision: Union[str, None] = 'ffbdfeebd16c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create billing_update_retries table
    op.create_table('billing_update_retries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(), nullable=False),
        sa.Column('new_quantity', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('last_attempt', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('next_retry_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    # Create index on org_id for performance
    op.create_index(op.f('ix_billing_update_retries_org_id'), 'billing_update_retries', ['org_id'], unique=False)
    # Create index on next_retry_at for efficient querying
    op.create_index(op.f('ix_billing_update_retries_next_retry_at'), 'billing_update_retries', ['next_retry_at'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_billing_update_retries_next_retry_at'), table_name='billing_update_retries')
    op.drop_index(op.f('ix_billing_update_retries_org_id'), table_name='billing_update_retries')
    # Drop table
    op.drop_table('billing_update_retries')
