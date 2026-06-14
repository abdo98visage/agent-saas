"""add user_activities table and last_seen_at to users

Revision ID: add_user_activity_last_seen
Revises: 
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_user_activity_last_seen'
down_revision = '002_add_soul_md_invite'
branch_labels = None
depends_on = None


def upgrade():
    # Add last_seen_at to users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_seen_at', sa.DateTime(), nullable=True))

    with op.batch_alter_table('kpis', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tokens_used', sa.BigInteger(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('total_cost', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('models_used', postgresql.JSONB, nullable=False, server_default='{}'))

    # Create user_activities table
    op.create_table(
        'user_activities',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('action', sa.String(50), nullable=False, index=True),
        sa.Column('details', postgresql.JSONB, nullable=True, server_default='{}'),
        sa.Column('session_id', sa.UUID(), sa.ForeignKey('sessions.id'), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade():
    op.drop_table('user_activities')
    with op.batch_alter_table('kpis', schema=None) as batch_op:
        batch_op.drop_column('models_used')
        batch_op.drop_column('total_cost')
        batch_op.drop_column('tokens_used')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('last_seen_at')
