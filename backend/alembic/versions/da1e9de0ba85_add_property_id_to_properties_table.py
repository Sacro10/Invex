"""Add property_id to properties table

Revision ID: da1e9de0ba85
Revises: 0fe3741913fa
Create Date: 2025-12-31 16:07:28.851828

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da1e9de0ba85'
down_revision: Union[str, None] = '0fe3741913fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('properties', sa.Column('property_id', sa.String(), nullable=False))
    op.create_unique_constraint('uq_properties_property_id', 'properties', ['property_id'])


def downgrade() -> None:
    op.drop_constraint('uq_properties_property_id', 'properties', type_='unique')
    op.drop_column('properties', 'property_id')
