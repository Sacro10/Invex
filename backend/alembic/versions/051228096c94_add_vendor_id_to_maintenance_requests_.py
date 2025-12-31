"""Add vendor_id to maintenance_requests table

Revision ID: 051228096c94
Revises: 65dc22250eef
Create Date: 2025-12-31 17:26:44.865668

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '051228096c94'
down_revision: Union[str, None] = '65dc22250eef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('maintenance_requests') as batch_op:
        batch_op.add_column(sa.Column('vendor_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_maintenance_requests_vendor_id',
            'vendors',
            ['vendor_id'], ['id'],
            ondelete='SET NULL'
        )
        batch_op.create_index('ix_maintenance_requests_vendor_id', ['vendor_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('maintenance_requests') as batch_op:
        batch_op.drop_index('ix_maintenance_requests_vendor_id')
        batch_op.drop_constraint('fk_maintenance_requests_vendor_id', type_='foreignkey')
        batch_op.drop_column('vendor_id')
