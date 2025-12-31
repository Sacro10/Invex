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
    op.add_column('maintenance_requests', sa.Column('vendor_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_maintenance_requests_vendor_id',
        'maintenance_requests', 'vendors',
        ['vendor_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index(op.f('ix_maintenance_requests_vendor_id'), 'maintenance_requests', ['vendor_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_maintenance_requests_vendor_id'), table_name='maintenance_requests')
    op.drop_constraint('fk_maintenance_requests_vendor_id', 'maintenance_requests', type_='foreignkey')
    op.drop_column('maintenance_requests', 'vendor_id')
