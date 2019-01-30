"""Add OldSlug table

Revision ID: 464b02fb1006
Revises: 4227dfe5456c
Create Date: 2019-01-30 19:56:25.220864

"""

# revision identifiers, used by Alembic.
revision = '464b02fb1006'
down_revision = '4227dfe5456c'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.create_table('old_slug',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('discussion_id', sa.Integer,
                  sa.ForeignKey('discussion.id', ondelete="CASCADE",
                                onupdate="CASCADE"),nullable=False),
        sa.Column('slug', sa.CoerceUnicode,nullable=False, unique=True, index=True),
        sa.Column('redirection_slug', sa.CoerceUninceode, nullable=False, unique=True, index=True))


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_table("old_slug")
