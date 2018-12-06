"""migrate_description_side_in_thematic_to_quote_in_announcement

Revision ID: 798b61d37451
Revises: de9ade82771c
Create Date: 2018-12-04 17:01:21.940162

"""

# revision identifiers, used by Alembic.
revision = '798b61d37451'
down_revision = 'de9ade82771c'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_column('thematic', "video_description_side_id")
        op.add_column('announce', sa.Column('quote_id',
            sa.Integer, sa.ForeignKey('langstring.id'))
        )

    # Do stuff with the app's models here.
    from assembl import models as m
    db = m.get_session_maker()()
    with transaction.manager:
        thematics = db.query(m.Thematic).all()
        announcements = db.query(m.IdeaAnnouncement)
        for thematic in thematics:
        	thematic.sqla_type = 'idea'
        	thematic_announcement = announcements.filter(m.IdeaAnnouncement.idea_id==thematic.id).first()
        	if thematic_announcement:
        		thematic_announcement.quote_id = thematic.video_description_side_id

    with context.begin_transaction():
    	op.drop_table('thematic')


def downgrade(pyramid_env):
    with context.begin_transaction():
		op.create_table(
            'thematic',
            sa.Column('id', sa.Integer, sa.ForeignKey(
                'idea.id'), primary_key=True),
            sa.Column('title_id', sa.Integer,
                sa.ForeignKey('langstring.id'), nullable=False),
            sa.Column('description_id', sa.Integer,
                sa.ForeignKey('langstring.id')),
            sa.Column('video_title_id', sa.Integer,
                sa.ForeignKey('langstring.id')),
            sa.Column('video_description_id', sa.Integer,
                sa.ForeignKey('langstring.id')),
            sa.Column('video_html_code', sa.UnicodeText),
            sa.Column('identifier', sa.String(60))
        )
        op.drop_column('announce', 'quote_id')
