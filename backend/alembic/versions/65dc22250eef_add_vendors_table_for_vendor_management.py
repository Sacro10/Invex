"""Add vendors table for vendor management

Revision ID: 65dc22250eef
Revises: da1e9de0ba85
Create Date: 2025-12-31 17:24:01.845374

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65dc22250eef'
down_revision: Union[str, None] = 'da1e9de0ba85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('vendors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('specialties', sa.String(), nullable=False),
        sa.Column('service_zip_codes', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vendors_id'), 'vendors', ['id'], unique=False)
    op.create_index(op.f('ix_vendors_org_id'), 'vendors', ['org_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_vendors_org_id'), table_name='vendors')
    op.drop_index(op.f('ix_vendors_id'), table_name='vendors')
    op.drop_table('vendors')
