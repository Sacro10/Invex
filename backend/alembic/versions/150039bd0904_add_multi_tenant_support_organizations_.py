"""Add multi-tenant support: organizations, users, org_id to all tables

Revision ID: 150039bd0904
Revises: 16bd06c8a1e1
Create Date: 2025-12-31 01:40:04.972115

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '150039bd0904'
down_revision: Union[str, None] = '16bd06c8a1e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create organizations table
    op.create_table('organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_organizations_id'), 'organizations', ['id'], unique=False)
    
    # Create users table with foreign key to organizations
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_org_id'), 'users', ['org_id'], unique=False)
    
    # Add org_id to existing tables using batch mode (SQLite compatibility)
    with op.batch_alter_table('tenant_screenings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('org_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.create_index(op.f('ix_tenant_screenings_org_id'), ['org_id'], unique=False)
        batch_op.create_foreign_key('fk_tenant_screenings_org_id_organizations', 'organizations', ['org_id'], ['id'], ondelete='CASCADE')
    
    with op.batch_alter_table('maintenance_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('org_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.create_index(op.f('ix_maintenance_requests_org_id'), ['org_id'], unique=False)
        batch_op.create_foreign_key('fk_maintenance_requests_org_id_organizations', 'organizations', ['org_id'], ['id'], ondelete='CASCADE')
    
    with op.batch_alter_table('rent_collections', schema=None) as batch_op:
        batch_op.add_column(sa.Column('org_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.create_index(op.f('ix_rent_collections_org_id'), ['org_id'], unique=False)
        batch_op.create_foreign_key('fk_rent_collections_org_id_organizations', 'organizations', ['org_id'], ['id'], ondelete='CASCADE')
    
    with op.batch_alter_table('lease_renewals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('org_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.create_index(op.f('ix_lease_renewals_org_id'), ['org_id'], unique=False)
        batch_op.create_foreign_key('fk_lease_renewals_org_id_organizations', 'organizations', ['org_id'], ['id'], ondelete='CASCADE')
    
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('org_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.create_index(op.f('ix_notifications_org_id'), ['org_id'], unique=False)
        batch_op.create_foreign_key('fk_notifications_org_id_organizations', 'organizations', ['org_id'], ['id'], ondelete='CASCADE')
    
    with op.batch_alter_table('properties', schema=None) as batch_op:
        batch_op.add_column(sa.Column('org_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.create_index(op.f('ix_properties_org_id'), ['org_id'], unique=False)
        batch_op.create_foreign_key('fk_properties_org_id_organizations', 'organizations', ['org_id'], ['id'], ondelete='CASCADE')
    
    with op.batch_alter_table('leases', schema=None) as batch_op:
        batch_op.add_column(sa.Column('org_id', sa.Integer(), nullable=False, server_default='1'))
        batch_op.create_index(op.f('ix_leases_org_id'), ['org_id'], unique=False)
        batch_op.create_foreign_key('fk_leases_org_id_organizations', 'organizations', ['org_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    # Drop foreign keys and columns from existing tables
    with op.batch_alter_table('leases', schema=None) as batch_op:
        batch_op.drop_constraint('fk_leases_org_id_organizations', type_='foreignkey')
        batch_op.drop_index(op.f('ix_leases_org_id'))
        batch_op.drop_column('org_id')
    
    with op.batch_alter_table('properties', schema=None) as batch_op:
        batch_op.drop_constraint('fk_properties_org_id_organizations', type_='foreignkey')
        batch_op.drop_index(op.f('ix_properties_org_id'))
        batch_op.drop_column('org_id')
    
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_constraint('fk_notifications_org_id_organizations', type_='foreignkey')
        batch_op.drop_index(op.f('ix_notifications_org_id'))
        batch_op.drop_column('org_id')
    
    with op.batch_alter_table('lease_renewals', schema=None) as batch_op:
        batch_op.drop_constraint('fk_lease_renewals_org_id_organizations', type_='foreignkey')
        batch_op.drop_index(op.f('ix_lease_renewals_org_id'))
        batch_op.drop_column('org_id')
    
    with op.batch_alter_table('rent_collections', schema=None) as batch_op:
        batch_op.drop_constraint('fk_rent_collections_org_id_organizations', type_='foreignkey')
        batch_op.drop_index(op.f('ix_rent_collections_org_id'))
        batch_op.drop_column('org_id')
    
    with op.batch_alter_table('maintenance_requests', schema=None) as batch_op:
        batch_op.drop_constraint('fk_maintenance_requests_org_id_organizations', type_='foreignkey')
        batch_op.drop_index(op.f('ix_maintenance_requests_org_id'))
        batch_op.drop_column('org_id')
    
    with op.batch_alter_table('tenant_screenings', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tenant_screenings_org_id_organizations', type_='foreignkey')
        batch_op.drop_index(op.f('ix_tenant_screenings_org_id'))
        batch_op.drop_column('org_id')
    
    # Drop users and organizations tables
    op.drop_table('users')
    op.drop_table('organizations')
