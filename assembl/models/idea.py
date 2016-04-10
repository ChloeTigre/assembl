# -*- coding: utf-8 -*-

from itertools import chain, groupby
from collections import defaultdict
from abc import ABCMeta, abstractmethod
from datetime import datetime

from bs4 import BeautifulSoup
from rdflib import URIRef
from sqlalchemy.orm import (
    relationship, backref, aliased, contains_eager, joinedload, deferred,
    column_property, with_polymorphic)
from sqlalchemy.orm.attributes import NO_VALUE
from sqlalchemy.sql import text, column
from sqlalchemy.sql.expression import union, bindparam, literal_column

from sqlalchemy import (
    Column,
    Boolean,
    Integer,
    String,
    Unicode,
    Float,
    UnicodeText,
    DateTime,
    ForeignKey,
    inspect,
    select,
    func,
)
from sqlalchemy.ext.associationproxy import association_proxy
from virtuoso.vmapping import IriClass, PatternIriClass
from virtuoso.alchemy import SparqlClause

from ..lib.utils import get_global_base_url
from ..nlp.wordcounter import WordCounter
from . import DiscussionBoundBase, HistoryMixin
from .discussion import Discussion
from ..semantic.virtuoso_mapping import (
    QuadMapPatternS, AssemblQuadStorageManager)
from ..auth import (
    CrudPermissions, P_READ, P_ADMIN_DISC, P_EDIT_IDEA,
    P_ADD_IDEA)
from ..semantic.namespaces import (
    SIOC, IDEA, ASSEMBL, DCTERMS, QUADNAMES, FOAF, RDF, VirtRDF)
from ..lib.sqla import (CrudOperation, get_model_watcher)
from assembl.views.traversal import (
    AbstractCollectionDefinition, CollectionDefinition)

if DiscussionBoundBase.using_virtuoso:
    from virtuoso.alchemy import Timestamp
else:
    from sqlalchemy.types import TIMESTAMP as Timestamp


class defaultdictlist(defaultdict):
    def __init__(self):
        super(defaultdictlist, self).__init__(list)


class IdeaVisitor(object):
    CUT_VISIT = object()
    __metaclass__ = ABCMeta

    @abstractmethod
    def visit_idea(self, idea, level, prev_result):
        pass

    def end_visit(self, idea, level, result, child_results):
        return result


class IdeaLinkVisitor(object):
    CUT_VISIT = object()
    __metaclass__ = ABCMeta

    @abstractmethod
    def visit_link(self, link):
        pass


class WordCountVisitor(IdeaVisitor):
    def __init__(self, langs, count_posts=True):
        self.counter = WordCounter(langs)
        self.count_posts = True

    def cleantext(self, text):
        return BeautifulSoup(text or '').get_text().strip()

    def visit_idea(self, idea, level, prev_result):
        if idea.short_title:
            self.counter.add_text(self.cleantext(idea.short_title), 2)
        if idea.long_title:
            self.counter.add_text(self.cleantext(idea.long_title))
        if idea.definition:
            self.counter.add_text(self.cleantext(idea.definition))
        if self.count_posts and level == 0:
            from .generic import Content
            related = Idea.get_related_posts_query(
                idea.discussion_id, idea.id).subquery()
            titles = set()
            # TODO maparent: Reoptimize
            for content in idea.db.query(
                    Content).join(
                    related, related.c.post_id == Content.id):
                body = content.body.first_original().value
                self.counter.add_text(self.cleantext(body), 0.5)
                title = content.subject.first_original().value
                title = self.cleantext(title)
                if title not in titles:
                    self.counter.add_text(title)
                    titles.add(title)

    def best(self, num=8):
        return self.counter.best(num)


class Idea(HistoryMixin, DiscussionBoundBase):
    """
    A core concept taken from the associated discussion
    """
    __tablename__ = "idea"
    ORPHAN_POSTS_IDEA_ID = 'orphan_posts'
    sqla_type = Column(String(60), nullable=False)
    rdf_type = Column(
        String(60), nullable=False, server_default='idea:GenericIdeaNode')

    long_title = Column(
        UnicodeText,
        info={'rdf': QuadMapPatternS(None, DCTERMS.alternative)})
    short_title = Column(
        UnicodeText,
        info={'rdf': QuadMapPatternS(None, DCTERMS.title)})
    definition = Column(
        UnicodeText,
        info={'rdf': QuadMapPatternS(None, DCTERMS.description)})
    hidden = Column(Boolean, server_default='0')
    last_modified = Column(Timestamp)
    # TODO: Make this autoupdate on change. see
    # http://stackoverflow.com/questions/1035980/update-timestamp-when-row-is-updated-in-postgresql

    creation_date = Column(
        DateTime, nullable=False, default=datetime.utcnow,
        info={'rdf': QuadMapPatternS(None, DCTERMS.created)})

    discussion_id = Column(Integer, ForeignKey(
        'discussion.id',
        ondelete='CASCADE',
        onupdate='CASCADE'),
        nullable=False,
        index=True,
        info={'rdf': QuadMapPatternS(None, SIOC.has_container)})

    discussion = relationship(
        Discussion,
        backref=backref(
            'ideas', order_by=creation_date,
            cascade="all, delete-orphan"),
        info={'rdf': QuadMapPatternS(None, ASSEMBL.in_conversation)}
    )

    #widget_id = deferred(Column(Integer, ForeignKey('widget.id')))
    #widget = relationship("Widget", backref=backref('ideas', order_by=creation_date))

    __mapper_args__ = {
        'polymorphic_identity': 'idea',
        'polymorphic_on': sqla_type,
        # Not worth it for now, as the only other class is RootIdea, and there
        # is only one per discussion - benoitg 2013-12-23
        #'with_polymorphic': '*'
    }

    @classmethod
    def special_quad_patterns(cls, alias_maker, discussion_id):
        discussion_alias = alias_maker.get_reln_alias(cls.discussion)
        return [
            QuadMapPatternS(
                None, RDF.type,
                IriClass(VirtRDF.QNAME_ID).apply(Idea.rdf_type),
                name=QUADNAMES.class_Idea_class),
            QuadMapPatternS(
                None, FOAF.homepage,
                PatternIriClass(
                    QUADNAMES.idea_external_link_iri,
                    # TODO: Use discussion.get_base_url.
                    # This should be computed outside the DB.
                    get_global_base_url() + '/%s/idea/local:Idea/%d', None,
                    ('slug', Unicode, False), ('id', Integer, False)).apply(
                    discussion_alias.slug, cls.id),
                name=QUADNAMES.idea_external_link_map)
        ]

    parents = association_proxy(
        'source_links', 'source',
        creator=lambda idea: IdeaLink(source=idea))

    parents_ts = association_proxy(
        'source_links_ts', 'source_ts',
        creator=lambda idea: IdeaLink(source=idea))

    children = association_proxy(
        'target_links', 'target',
        creator=lambda idea: IdeaLink(target=idea))

    def get_children(self):
        return self.db.query(Idea).join(
            IdeaLink, (IdeaLink.target_id == Idea.id)
            & (IdeaLink.tombstone_date == None)).filter(
            (IdeaLink.source_id == self.id)
            & (Idea.tombstone_date == None)
            ).order_by(IdeaLink.order).all()

    def get_parents(self):
        return self.db.query(Idea).join(
            IdeaLink, (IdeaLink.source_id == Idea.id)
            & (IdeaLink.tombstone_date == None)).filter(
            (IdeaLink.target_id == self.id)
            & (Idea.tombstone_date == None)).all()

    @property
    def parent_uris(self):
        return [Idea.uri_generic(l.source_id) for l in self.source_links]

    @property
    def widget_add_post_endpoint(self):
        # Only for api v2
        from pyramid.threadlocal import get_current_request
        from .widgets import Widget
        req = get_current_request() or {}
        ctx = getattr(req, 'context', {})
        if getattr(ctx, 'get_instance_of_class', None):
            # optional optimization
            widget = ctx.get_instance_of_class(Widget)
            if widget:
                if getattr(widget, 'get_add_post_endpoint', None):
                    return {widget.uri(): widget.get_add_post_endpoint(self)}
            else:
                return self.widget_ancestor_endpoints(self)

    def widget_ancestor_endpoints(self, target_idea=None):
        # HACK. Review consequences after test.
        target_idea = target_idea or self
        inherited = dict()
        for p in self.get_parents():
            inherited.update(p.widget_ancestor_endpoints(target_idea))
        inherited.update({
            widget.uri(): widget.get_add_post_endpoint(target_idea)
            for widget in self.widgets
            if getattr(widget, 'get_add_post_endpoint', None)
        })
        return inherited

    def copy(self, tombstone=None, **kwargs):
        kwargs.update(
            tombstone=tombstone,
            long_title=self.long_title,
            short_title=self.short_title,
            definition=self.definition,
            hidden=self.hidden,
            creation_date=self.creation_date,
            discussion=self.discussion)
        return super(Idea, self).copy(**kwargs)

    @classmethod
    def get_ancestors_query(
            cls, target_id=bindparam('root_id', type_=Integer),
            inclusive=True):
        if cls.using_virtuoso:
            if isinstance(target_id, list):
                raise NotImplemented()
            sql = text(
                """SELECT transitive t_in (1) t_out (2) T_DISTINCT T_NO_CYCLES
                    source_id, target_id FROM idea_idea_link
                    WHERE tombstone_date IS NULL"""
                ).columns(column('source_id'), column('target_id')).alias()
            select_exp = select([sql.c.source_id.label('id')]
                ).select_from(sql).where(sql.c.target_id==target_id)
        else:
            if isinstance(target_id, list):
                root_condition = IdeaLink.target_id.in_(target_id)
            else:
                root_condition = (IdeaLink.target_id == target_id)
            link = select(
                    [IdeaLink.source_id, IdeaLink.target_id]
                ).select_from(
                    IdeaLink
                ).where(
                    (IdeaLink.tombstone_date == None) &
                    (root_condition)
                ).cte(recursive=True)
            target_alias = aliased(link)
            sources_alias = aliased(IdeaLink)
            parent_link = sources_alias.target_id == target_alias.c.source_id
            parents = select(
                    [sources_alias.source_id, sources_alias.target_id]
                ).select_from(sources_alias).where(parent_link
                    & (sources_alias.tombstone_date == None))
            with_parents = link.union(parents)
            select_exp = select([with_parents.c.source_id.label('id')]
                ).select_from(with_parents)
        if inclusive:
            if isinstance(target_id, int):
                target_id = literal_column(str(target_id), Integer)
            elif isinstance(target_id, list):
                raise NotImplemented()
                # postgres: select * from unnest(ARRAY[1,6,7]) as id
            else:
                select_exp = select_exp.union(
                    select([target_id.label('id')]))
        return select_exp.alias()

    def get_all_ancestors(self, id_only=False):
        query = self.get_ancestors_query(self.id)
        if id_only:
            return list((id for (id,) in self.db.query(query)))
        else:
            return self.db.query(Idea).filter(Idea.id.in_(query)).all()

    @classmethod
    def get_descendants_query(
            cls, root_idea_id=bindparam('root_idea_id', type_=Integer),
            inclusive=True):
        if cls.using_virtuoso:
            sql = text(
                """SELECT transitive t_in (1) t_out (2) T_DISTINCT T_NO_CYCLES
                    source_id, target_id FROM idea_idea_link
                    WHERE tombstone_date IS NULL"""
                ).columns(column('source_id'), column('target_id')).alias()
            select_exp = select([sql.c.target_id.label('id')]
                ).select_from(sql).where(sql.c.source_id==root_idea_id)
        else:
            link = select(
                    [IdeaLink.source_id, IdeaLink.target_id]
                ).select_from(
                    IdeaLink
                ).where(
                    (IdeaLink.tombstone_date == None) &
                    (IdeaLink.source_id == root_idea_id)
                ).cte(recursive=True)
            source_alias = aliased(link)
            targets_alias = aliased(IdeaLink)
            parent_link = targets_alias.source_id == source_alias.c.target_id
            children = select(
                    [targets_alias.source_id, targets_alias.target_id]
                ).select_from(targets_alias).where(parent_link
                    & (targets_alias.tombstone_date == None))
            with_children = link.union(children)
            select_exp = select([with_children.c.target_id.label('id')]
                ).select_from(with_children)
        if inclusive:
            if isinstance(root_idea_id, int):
                root_idea_id = literal_column(str(root_idea_id), Integer)
            select_exp = select_exp.union(
                select([root_idea_id.label('id')]))
        return select_exp.alias()

    def get_all_descendants(self, id_only=False):
        query = self.get_descendants_query(self.id)
        if id_only:
            return list((id for (id,) in self.db.query(query)))
        else:
            return self.db.query(Idea).filter(Idea.id.in_(query)).all()

    def get_order_from_first_parent(self):
        return self.source_links[0].order if self.source_links else None

    def get_order_from_first_parent_ts(self):
        return self.source_links_ts[0].order if self.source_links_ts else None

    def get_first_parent_uri(self):
        for link in self.source_links:
            return Idea.uri_generic(link.source_id)

    def get_first_parent_uri_ts(self):
        return Idea.uri_generic(
            self.source_links_ts[0].source_id
        ) if self.source_links_ts else None

    @classmethod
    def get_related_posts_query(
            cls,
            discussion_id=bindparam('discussion_id', type_=Integer),
            root_idea_id=bindparam('root_idea_id', type_=Integer)):
        from .post import Post
        from .generic import Content
        from .idea_content_link import IdeaContentLink, IdeaContentPositiveLink
        if isinstance(discussion_id, int):
            discussion_id = literal_column(str(discussion_id), Integer)
        if isinstance(root_idea_id, int):
            root_idea_id = literal_column(str(root_idea_id), Integer)
        dq = cls.get_descendants_query(root_idea_id)

        RootPost = with_polymorphic(
            Post, [], Post.__table__, aliased=False, flat=True)
        SubPost = with_polymorphic(
            Post, [], Post.__table__, aliased=False, flat=True)
        # This should be a join but creates a subquery
        SubPostContent = with_polymorphic(
            Content, [], Content.__table__, aliased=False, flat=True)
        ICL = with_polymorphic(
            IdeaContentLink, [], IdeaContentLink.__table__,
            aliased=False, flat=True)
        # This should be a join but creates a subquery
        ICPL = with_polymorphic(
            IdeaContentPositiveLink, [], IdeaContentPositiveLink.__table__,
            aliased=False, flat=True)

        return cls.default_db.query(
                SubPost.id.distinct().label("post_id")
            ).select_from(dq
            ).join(
                cls,
                (dq.c.id == cls.id) &
                (cls.discussion_id == discussion_id) &
                (cls.tombstone_date == None) &
                (cls.hidden == False)
            ).join(ICL, dq.c.id == ICL.idea_id
            ).join(ICPL, ICL.id == ICPL.id
            ).join(
                RootPost, ICL.content_id == RootPost.id
            ).join(
                SubPost,
                (SubPost.ancestry != '') & (SubPost.ancestry.like(
                    RootPost.ancestry.op('||')(
                        RootPost.id.cast(String).op("||")(",%"))) |
                (SubPost.id == RootPost.id))
            ).join(
                SubPostContent,
                (SubPostContent.id == SubPost.id) &
                (SubPostContent.discussion_id == discussion_id) &
                (SubPostContent.hidden == False)
            )

    @classmethod
    def _get_orphan_posts_statement(
            cls, discussion_id=bindparam('discussion_id', type_=Integer)):
        """ Requires discussion_id bind parameters
        Excludes synthesis posts """
        from .idea_content_link import IdeaContentPositiveLink
        from .generic import Content
        from .post import Post
        if isinstance(discussion_id, int):
            discussion_id = literal_column(str(discussion_id), Integer)
        RootPost = with_polymorphic(
            Post, [], Post.__table__, aliased=True, flat=True)
        SubPost = with_polymorphic(
            Post, [], Post.__table__, aliased=True, flat=True)
        Post1 = with_polymorphic(
            Post, [], Post.__table__.join(Content.__table__),
            aliased=True, flat=True)
        subq = cls.default_db.query(
            SubPost.id.distinct().label("post_id")
            ).join(
                RootPost,
                (SubPost.ancestry != '') & SubPost.ancestry.like(
                    RootPost.ancestry.op('||')(
                        RootPost.id.cast(String).op("||")(",%"))) |
                (SubPost.id==RootPost.id)
            ).join(
                IdeaContentPositiveLink,
                IdeaContentPositiveLink.content_id == RootPost.id
            ).join(cls, IdeaContentPositiveLink.idea_id == cls.id
            ).filter(cls.discussion_id == discussion_id,
                cls.tombstone_date == None, cls.hidden == False
            )

        return cls.default_db.query(
            Post1.id.label("post_id")
            ).filter(Post1.discussion_id == discussion_id,
                     Post1.type != 'synthesis_post',
                     Post1.hidden == False).except_(subq)

    @property
    def num_posts(self):
        """ This is extremely naive and slow, but as this is all temp code
        until we move to a graph database, it will probably do for now """
        return self.get_related_posts_query(
            self.discussion_id, self.id).count()

    @property
    def num_read_posts(self):
        """ Worse than above... but temporary """
        connection = self.db.connection()
        user_id = connection.info.get('userid', None)
        return self.num_read_posts_for(user_id)

    @property
    def num_total_and_read_posts(self):
        connection = self.db.connection()
        user_id = connection.info.get('userid', None)
        if user_id:
            return self.num_total_and_read_posts_for(user_id)
        else:
            return (self.num_posts, 0)

    def num_read_posts_for(self, user_id):
        if not user_id:
            return 0
        from .generic import Content
        from .action import Action, ActionOnPost
        from sqlalchemy.sql.functions import count
        if not user_id:
            return 0
        user_id = literal_column(str(user_id), Integer)
        query = self.get_related_posts_query(self.discussion_id, self.id)
        SubPostContent = [
            x.selectable for x in query._join_entities
            if x.mapper.class_ == Content][0]
        action_on_post = with_polymorphic(
            ActionOnPost, [], ActionOnPost.__table__, aliased=False, flat=True)
        action = with_polymorphic(
            Action, [], Action.__table__, aliased=False, flat=True)
        query2 = query.join(
                action_on_post, action_on_post.post_id == SubPostContent.c.id
            ).join(
                action,
                (action_on_post.id == action.id) &
                (action.actor_id == user_id) &
                (action.tombstone_date == None) &
                (action.type == 'version:ReadStatusChange_P')
            )
        return query2.count()

    def num_total_and_read_posts_for(self, user_id):
        from .generic import Content
        from .action import Action, ActionOnPost
        from sqlalchemy.sql.functions import count, min
        if not user_id:
            return 0
        user_id = literal_column(str(user_id), Integer)
        query = self.get_related_posts_query(self.discussion_id, self.id)
        SubPostContent = [
            x.selectable for x in query._join_entities
            if x.mapper.class_ == Content][0]
        action_on_post = with_polymorphic(
            ActionOnPost, [], ActionOnPost.__table__, aliased=False, flat=True)
        action = with_polymorphic(
            Action, [], Action.__table__, aliased=False, flat=True)
        return query.outerjoin(
                action_on_post, action_on_post.post_id == SubPostContent.c.id
            ).outerjoin(
                action,
                (action_on_post.id == action.id) &
                (action.actor_id == user_id) &
                (action.tombstone_date == None) &
                (action.type == 'version:ReadStatusChange_P')
            ).with_entities(
                count(SubPostContent.c.id.distinct()).label("post_count"),
                count(action.id.distinct()).label("read_count")
            ).first()

    def prefetch_descendants(self):
        # TODO: descendants only. Let's just prefetch all ideas.
        self.db.query(Idea).filter_by(
            discussion_id=self.discussion_id, tombstone_date=None).all()
        self.db.query(IdeaLink).join(
            Idea, IdeaLink.source_id == Idea.id).filter(
            Idea.discussion_id == self.discussion_id,
            IdeaLink.tombstone_date == None).all()

    def visit_ideas_depth_first(self, idea_visitor):
        self.prefetch_descendants()
        return self._visit_ideas_depth_first(idea_visitor, set(), 0, None)

    def _visit_ideas_depth_first(
            self, idea_visitor, visited, level, prev_result):
        if self in visited:
            # not necessary in a tree, but let's start to think graph.
            return False
        result = idea_visitor.visit_idea(self, level, prev_result)
        visited.add(self)
        child_results = []
        if result is not IdeaVisitor.CUT_VISIT:
            for child in self.get_children():
                r = child._visit_ideas_depth_first(
                    idea_visitor, visited, level+1, result)
                if r:
                    child_results.append(r)
        return idea_visitor.end_visit(self, level, result, child_results)

    def visit_ideas_breadth_first(self, idea_visitor):
        self.prefetch_descendants()
        result = idea_visitor.visit_idea(self, 0, None)
        visited = {self}
        if result is not IdeaVisitor.CUT_VISIT:
            return self._visit_ideas_breadth_first(
                idea_visitor, visited, 1, result)

    def _visit_ideas_breadth_first(
            self, idea_visitor, visited, level, prev_result):
        children = []
        result = True
        child_results = []
        for child in self.get_children():
            if child in visited:
                continue
            result = idea_visitor.visit_idea(child, level, prev_result)
            visited.add(child)
            if result != IdeaVisitor.CUT_VISIT:
                children.append(child)
                if result:
                    child_results.append(result)
        for child in children:
            child._visit_ideas_breadth_first(
                idea_visitor, visited, level+1, result)
        return idea_visitor.end_visit(self, level, prev_result, child_results)

    def most_common_words(self, lang=None, num=8):
        if lang:
            langs = (lang,)
        else:
            langs = self.discussion.discussion_locales
        word_counter = WordCountVisitor(langs)
        self.visit_ideas_depth_first(word_counter)
        return word_counter.best(num)

    @property
    def most_common_words_prop(self):
        return self.most_common_words()

    def get_siblings_of_type(self, cls):
        # TODO: optimize
        siblings = set(chain(*(p.children for p in self.get_parents())))
        if siblings:
            siblings.remove(self)
        return [c for c in siblings if isinstance(c, cls)]

    def get_synthesis_contributors(self, id_only=True):
        # author of important extracts
        from .idea_content_link import Extract
        from .auth import AgentProfile
        from .post import Post
        from .generic import Content
        from sqlalchemy.sql.functions import count
        subquery = self.get_descendants_query(self.id)
        query = self.db.query(
            Post.creator_id
            ).join(Extract
            ).join(subquery, Extract.idea_id == subquery.c.id
            ).filter(Extract.important == True
            ).group_by(Post.creator_id
            ).order_by(count(Extract.id).desc())
        if id_only:
            return [AgentProfile.uri_generic(a) for (a,) in query]
        else:
            ids = [x for (x,) in query]
            if not ids:
                return []
            agents = {a.id: a for a in self.db.query(AgentProfile).filter(
                AgentProfile.id.in_(ids))}
            return [agents[id] for id in ids]

    def get_contributors(self):
        from .post import Post
        from sqlalchemy.sql.functions import count
        query = self.get_related_posts_query(self.discussion_id, self.id)
        post_entities = {
            e.selectable for e in query._join_entities
            if e.mapper.class_ == Post}
        sub_post = query._entities[0].entity_zero.selectable
        post_entities.remove(sub_post)
        pivot_post = post_entities.pop()
        query2 = query.group_by(
            sub_post.c.creator_id
            ).with_entities(sub_post.c.creator_id
            ).order_by(
                count(pivot_post.c.id.distinct()).desc(),
                count(sub_post.c.id.distinct()).desc())

        return ['local:AgentProfile/' + str(i) for (i,) in query2]

    def get_discussion_id(self):
        return self.discussion_id or self.discussion.id

    def get_definition_preview(self):
        body = self.definition.strip()
        target_len = 120
        shortened = False
        html_len = 2 * target_len
        while True:
            text = BeautifulSoup(body[:html_len]).get_text().strip()
            if html_len >= len(body) or len(text) > target_len:
                shortened = html_len < len(body)
                body = text
                break
            html_len += target_len
        if len(body) > target_len:
            body = body[:target_len].rsplit(' ', 1)[0].rstrip() + ' '
        elif shortened:
            body += ' '
        return body

    def get_url(self):
        from assembl.lib.frontend_urls import FrontendUrls
        frontendUrls = FrontendUrls(self.discussion)
        return frontendUrls.get_idea_url(self)

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        return (cls.discussion_id == discussion_id,)

    def send_to_changes(self, connection=None, operation=CrudOperation.UPDATE,
                        discussion_id=None, view_def="changes"):
        connection = connection or self.db.connection()
        if self.is_tombstone:
            self.tombstone().send_to_changes(
                connection, CrudOperation.DELETE, discussion_id, view_def)
        else:
            super(Idea, self).send_to_changes(
                connection, operation, discussion_id, view_def)
        watcher = get_model_watcher()
        if operation == CrudOperation.UPDATE:
            watcher.processIdeaModified(self.id, 0)  # no versions yet.
        elif operation == CrudOperation.DELETE:
            watcher.processIdeaDeleted(self.id)
        elif operation == CrudOperation.CREATE:
            watcher.processIdeaCreated(self.id)

    def __repr__(self):
        r = super(Idea, self).__repr__()
        title = self.short_title or ""
        return r[:-1] + title.encode("ascii", "ignore") + ">"

    @classmethod
    def invalidate_ideas(cls, discussion_id, post_id):
        raise NotImplemented()

    @classmethod
    def get_idea_ids_showing_post(cls, post_id):
        "Given a post, give the ID of the ideas that show this message"
        # This works because of a virtuoso bug...
        # where DISTINCT gives IDs instead of URIs.
        from sqlalchemy.sql.functions import func
        from .idea_content_link import IdeaContentPositiveLink
        (idea_link_ids,)  = cls.default_db.query(
            func.idea_content_links_above_post(post_id)).first()
        if not idea_link_ids:
            return []
        idea_link_ids = [int(id) for id in idea_link_ids.split(',') if id]
        # This could be combined with previous in postgres.
        root_ideas = cls.default_db.query(
                IdeaContentPositiveLink.idea_id.distinct()
            ).filter(
                IdeaContentPositiveLink.idea_id != None,
                IdeaContentPositiveLink.id.in_(idea_link_ids)).all()
        if not root_ideas:
            return []
        root_ideas = [x for (x,) in root_ideas]
        if cls.using_virtuoso:
            # wasteful
            query = cls.get_ancestors_query(inclusive=False)
            ancestors_lists = [
                cls.default_db.query(query.params(root_id=id)).all()
                for id in root_ideas]
            ancestors = set(root_ideas)
            for ancestors_list in ancestors_lists:
                ancestors.update((x for (x,) in ancestors_list))
            return list(ancestors)
        else:
            ancestors = cls.default_db.query(
                cls.get_ancestors_query(root_ideas, False))
            ancestors = {x for (x,) in ancestors}
            ancestors.update(root_ideas)
            return list(ancestors)

    @classmethod
    def idea_read_counts(cls, discussion_id, post_id, user_id):
        """Given a post and a user, give the total and read count
            of posts for each affected idea"""
        idea_ids = cls.get_idea_ids_showing_post(post_id)
        if not idea_ids:
            return []
        ideas = cls.default_db.query(cls).filter(cls.id.in_(idea_ids))
        return [(idea.id, idea.num_read_posts_for(user_id))
                for idea in ideas]

    def get_widget_creation_urls(self):
        from .widgets import GeneratedIdeaWidgetLink
        return [wl.context_url for wl in self.widget_links
                if isinstance(wl, GeneratedIdeaWidgetLink)]

    # def get_notifications(self):
    #     # Dead code?
    #     from .widgets import BaseIdeaWidgetLink
    #     for widget_link in self.widget_links:
    #         if not isinstance(self, BaseIdeaWidgetLink):
    #             continue
    #         for n in widget_link.widget.has_notification():
    #             yield n

    @classmethod
    def get_all_idea_links(cls, discussion_id):
        target = aliased(cls)
        source = aliased(cls)
        return cls.default_db.query(
            IdeaLink).join(
            source, source.id == IdeaLink.source_id).join(
            target, target.id == IdeaLink.target_id).filter(
            target.discussion_id == discussion_id).filter(
            source.discussion_id == discussion_id).filter(
            IdeaLink.tombstone_date == None).all()

    @classmethod
    def extra_collections(cls):
        from .votes import AbstractIdeaVote
        from .widgets import (
            Widget, IdeaWidgetLink, VotedIdeaWidgetLink, InspirationWidget)
        from .idea_content_link import (
            IdeaRelatedPostLink, IdeaContentWidgetLink)
        from .generic import Content

        class ChildIdeaCollectionDefinition(AbstractCollectionDefinition):
            def __init__(self, cls):
                super(ChildIdeaCollectionDefinition, self).__init__(cls, Idea)

            def decorate_query(self, query, owner_alias, last_alias, parent_instance, ctx):
                parent = owner_alias
                children = last_alias
                return query.join(
                    IdeaLink, IdeaLink.target_id == children.id).join(
                    parent, IdeaLink.source_id == parent.id).filter(
                    IdeaLink.source_id == parent_instance.id,
                    IdeaLink.tombstone_date == None,
                    children.tombstone_date == None)

            def decorate_instance(
                    self, instance, parent_instance, assocs, user_id,
                    ctx, kwargs):
                if isinstance(instance, Idea):
                    assocs.append(IdeaLink(
                        source=parent_instance, target=instance,
                        **self.filter_kwargs(
                            IdeaLink, kwargs)))

            def contains(self, parent_instance, instance):
                return instance.db.query(
                    IdeaLink).filter_by(
                    source=parent_instance, target=instance
                    ).count() > 0

        class AncestorWidgetsCollectionDefinition(AbstractCollectionDefinition):
            # For widgets which represent general configuration.

            def __init__(self, cls, widget_subclass=None):
                super(AncestorWidgetsCollectionDefinition, self).__init__(cls, Widget)
                self.widget_subclass = widget_subclass

            def decorate_query(self, query, owner_alias, last_alias, parent_instance, ctx):
                parent = owner_alias
                widgets = last_alias
                ancestry = parent_instance.get_ancestors_query(
                    parent_instance.id)
                ancestors = aliased(Idea)
                iwlink = aliased(IdeaWidgetLink)
                query = query.join(iwlink).join(ancestors).filter(
                    ancestors.id.in_(ancestry)).join(
                    parent, parent.id == parent_instance.id)
                if self.widget_subclass is not None:
                    query = query.filter(iwlink.widget.of_type(self.widget_subclass))
                return query

            def decorate_instance(
                    self, instance, parent_instance, assocs, user_id,
                    ctx, kwargs):
                if isinstance(instance, Content):
                    assocs.append(
                        IdeaContentWidgetLink(
                            content=instance, widget=parent_instance,
                            creator_id=instance.creator_id,
                            **self.filter_kwargs(
                                IdeaContentWidgetLink, kwargs)))

            def contains(self, parent_instance, instance):
                ancestors = aliased(Idea)
                iwlink = aliased(IdeaWidgetLink)
                ancestry = parent_instance.get_ancestors_query(
                    parent_instance.id)
                query = instance.db.query(Widget).join(iwlink).join(
                    ancestors).filter(ancestors.id.in_(ancestry)).filter(
                    Widget.id == instance.id)
                if self.widget_subclass is not None:
                    query = query.filter(iwlink.widget.of_type(self.widget_subclass))
                return query.count() > 0

        class LinkedPostCollectionDefinition(AbstractCollectionDefinition):
            def __init__(self, cls):
                super(LinkedPostCollectionDefinition, self).__init__(
                    cls, Content)

            def decorate_query(self, query, owner_alias, last_alias, parent_instance, ctx):
                return query.join(IdeaRelatedPostLink, owner_alias)

            def decorate_instance(
                    self, instance, parent_instance, assocs, user_id,
                    ctx, kwargs):
                # This is going to spell trouble: Sometimes we'll have creator,
                # other times creator_id
                if isinstance(instance, Content):
                    assocs.append(
                        IdeaRelatedPostLink(
                            content=instance, idea=parent_instance,
                            creator_id=instance.creator_id,
                            **self.filter_kwargs(
                                IdeaRelatedPostLink, kwargs)))

            def contains(self, parent_instance, instance):
                return instance.db.query(
                    IdeaRelatedPostLink).filter_by(
                    content=instance, idea=parent_instance
                    ).count() > 0

        class WidgetPostCollectionDefinition(AbstractCollectionDefinition):
            def __init__(self, cls):
                super(WidgetPostCollectionDefinition, self).__init__(
                    cls, Content)

            def decorate_query(self, query, owner_alias, last_alias, parent_instance, ctx):
                from .post import IdeaProposalPost
                idea = owner_alias
                query = query.join(IdeaContentWidgetLink).join(
                    idea,
                    IdeaContentWidgetLink.idea_id == parent_instance.id)
                if Content in chain(*(
                        mapper.entities for mapper in query._entities)):
                    query = query.options(
                        contains_eager(Content.widget_idea_links))
                        # contains_eager(Content.extracts) seems to slow things down instead
                # Filter out idea proposal posts
                query = query.filter(last_alias.type.notin_(
                    IdeaProposalPost.polymorphic_identities()))
                return query

            def decorate_instance(
                    self, instance, parent_instance, assocs, user_id,
                    ctx, kwargs):
                # This is going to spell trouble: Sometimes we'll have creator,
                # other times creator_id
                if isinstance(instance, Content):
                    if parent_instance.proposed_in_post:
                        instance.set_parent(parent_instance.proposed_in_post)
                    assocs.append(
                        IdeaContentWidgetLink(
                            content=instance, idea=parent_instance,
                            creator_id=instance.creator_id,
                            **self.filter_kwargs(
                                IdeaContentWidgetLink, kwargs)))
                    instance.hidden = True

            def contains(self, parent_instance, instance):
                return instance.db.query(
                    IdeaContentWidgetLink).filter_by(
                    content=instance, idea=parent_instance
                    ).count() > 0

        class ActiveShowingWidgetsCollection(CollectionDefinition):
            def __init__(self, cls):
                super(ActiveShowingWidgetsCollection, self).__init__(
                    cls, cls.active_showing_widget_links)
            def decorate_query(self, query, owner_alias, last_alias, parent_instance, ctx):
                from .widgets import IdeaShowingWidgetLink
                idea = owner_alias
                widget_idea_link = last_alias
                query = query.join(
                    idea, widget_idea_link.idea).join(
                    Widget, widget_idea_link.widget).filter(
                    Widget.test_active(),
                    widget_idea_link.type.in_(
                        IdeaShowingWidgetLink.polymorphic_identities()),
                    idea.id == parent_instance.id)
                return query

        return {'children': ChildIdeaCollectionDefinition(cls),
                'linkedposts': LinkedPostCollectionDefinition(cls),
                'widgetposts': WidgetPostCollectionDefinition(cls),
                'ancestor_widgets': AncestorWidgetsCollectionDefinition(cls),
                'ancestor_inspiration_widgets': AncestorWidgetsCollectionDefinition(
                    cls, InspirationWidget),
                'active_showing_widget_links': ActiveShowingWidgetsCollection(cls)}

    def widget_link_signatures(self):
        from .widgets import Widget
        return [
            {'widget': Widget.uri_generic(l.widget_id),
             '@type': l.external_typename()}
            for l in self.widget_links]

    def active_widget_uris(self):
        from .widgets import Widget
        return [Widget.uri_generic(l.widget_id)
                for l in self.active_showing_widget_links]

    crud_permissions = CrudPermissions(
        P_ADD_IDEA, P_READ, P_EDIT_IDEA, P_ADMIN_DISC, P_ADMIN_DISC,
        P_ADMIN_DISC)


class RootIdea(Idea):
    """
    The root idea.  It represents the discussion.

    If has implicit links to all content and posts in the discussion.
    """
    root_for_discussion = relationship(
        Discussion,
        backref=backref('root_idea', uselist=False),
    )

    __mapper_args__ = {
        'polymorphic_identity': 'root_idea',
    }

    @property
    def num_posts(self):
        """ In the root idea, this is the count of all mesages in the system """
        from .post import Post
        result = self.db.query(Post).filter(
            Post.discussion_id == self.discussion_id,
            Post.hidden==False
        ).count()
        return int(result)

    @property
    def num_total_and_read_posts(self):
        return (self.num_posts, self.num_read_posts)

    @property
    def num_orphan_posts(self):
        "The number of posts unrelated to any idea in the current discussion"
        return Idea._get_orphan_posts_statement(self.discussion_id).count()

    @property
    def num_synthesis_posts(self):
        """ In the root idea, this is the count of all mesages in the system """
        from .post import Post, SynthesisPost
        result = self.db.query(SynthesisPost).filter(
            Post.discussion_id == self.discussion_id
        ).count()
        return int(result)

    def discussion_topic(self):
        return self.discussion.topic

    crud_permissions = CrudPermissions(P_ADMIN_DISC)


class IdeaLink(HistoryMixin, DiscussionBoundBase):
    """
    A generic link between two ideas

    If a parent-child relation, the parent is the source, the child the target.
    Beware: it's reversed in the RDF model. We will change things around.
    """
    __tablename__ = 'idea_idea_link'
    rdf_class = IDEA.InclusionRelation
    rdf_type = Column(
        String(60), nullable=False, server_default='idea:InclusionRelation')
    source_id = Column(
        Integer, ForeignKey(
            'idea.id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True)
        #info={'rdf': QuadMapPatternS(None, IDEA.target_idea)})
    target_id = Column(Integer, ForeignKey(
        'idea.id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True)
    source = relationship(
        'Idea',
        primaryjoin="and_(Idea.id==IdeaLink.source_id, "
                    "IdeaLink.tombstone_date == None, "
                    "Idea.tombstone_date == None)",
        backref=backref('target_links', cascade="all, delete-orphan"),
        foreign_keys=(source_id))
    target = relationship(
        'Idea',
        primaryjoin="and_(Idea.id==IdeaLink.target_id, "
                    "IdeaLink.tombstone_date == None, "
                    "Idea.tombstone_date == None)",
        backref=backref('source_links', cascade="all, delete-orphan"),
        foreign_keys=(target_id))
    source_ts = relationship(
        'Idea',
        backref=backref('target_links_ts', cascade="all, delete-orphan"),
        foreign_keys=(source_id))
    target_ts = relationship(
        'Idea',
        backref=backref('source_links_ts', cascade="all, delete-orphan"),
        foreign_keys=(target_id))
    order = Column(
        Float, nullable=False, default=0.0,
        info={'rdf': QuadMapPatternS(None, ASSEMBL.link_order)})

    @classmethod
    def base_conditions(cls, alias=None, alias_maker=None):
        if alias_maker is None:
            idea_link = alias or cls
            source_idea = Idea
        else:
            idea_link = alias or alias_maker.alias_from_class(cls)
            source_idea = alias_maker.alias_from_relns(idea_link.source)

        # Assume tombstone status of target is similar to source, for now.
        return ((idea_link.tombstone_date == None),
                (idea_link.source_id == source_idea.id),
                (source_idea.tombstone_date == None))

    @classmethod
    def special_quad_patterns(cls, alias_maker, discussion_id):
        idea_link = alias_maker.alias_from_class(cls)
        target_alias = alias_maker.alias_from_relns(cls.target)
        source_alias = alias_maker.alias_from_relns(cls.source)
        # Assume tombstone status of target is similar to source, for now.
        conditions = [(idea_link.target_id == target_alias.id),
                      (target_alias.tombstone_date == None)]
        if discussion_id:
            conditions.append((target_alias.discussion_id == discussion_id))
        return [
            QuadMapPatternS(
                Idea.iri_class().apply(idea_link.source_id),
                IDEA.includes,
                Idea.iri_class().apply(idea_link.target_id),
                conditions=conditions,
                name=QUADNAMES.idea_inclusion_reln),
            QuadMapPatternS(
                cls.iri_class().apply(idea_link.id),
                IDEA.source_idea,  # Note that RDF is inverted
                Idea.iri_class().apply(idea_link.target_id),
                conditions=conditions,
                name=QUADNAMES.col_pattern_IdeaLink_target_id
                #exclude_base_condition=True
                ),
            QuadMapPatternS(
                cls.iri_class().apply(idea_link.id),
                IDEA.target_idea,
                Idea.iri_class().apply(idea_link.source_id),
                name=QUADNAMES.col_pattern_IdeaLink_source_id
                ),
            QuadMapPatternS(
                None, RDF.type, IriClass(VirtRDF.QNAME_ID).apply(IdeaLink.rdf_type),
                name=QUADNAMES.class_IdeaLink_class),
        ]

    def copy(self, tombstone=None, **kwargs):
        kwargs.update(
            tombstone=tombstone,
            order=self.order,
            source_id=self.source_id,
            target_id=self.target_id)
        return super(IdeaLink, self).copy(**kwargs)

    def get_discussion_id(self):
        source = self.source_ts or Idea.get(self.source_id)
        return source.get_discussion_id()

    def send_to_changes(self, connection=None, operation=CrudOperation.UPDATE,
                        discussion_id=None, view_def="changes"):
        connection = connection or self.db.connection()
        if self.is_tombstone:
            self.tombstone().send_to_changes(
                connection, CrudOperation.DELETE, discussion_id, view_def)
        else:
            super(IdeaLink, self).send_to_changes(
                connection, operation, discussion_id, view_def)

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        if alias_maker is None:
            idea_link = cls
            source_idea = Idea
        else:
            idea_link = alias_maker.alias_from_class(cls)
            source_idea = alias_maker.alias_from_relns(idea_link.source)
        return ((idea_link.source_id == source_idea.id),
                (source_idea.discussion_id == discussion_id))

    crud_permissions = CrudPermissions(
        P_ADD_IDEA, P_READ, P_EDIT_IDEA, P_EDIT_IDEA, P_EDIT_IDEA, P_EDIT_IDEA)

    discussion = relationship(
        Discussion, viewonly=True, uselist=False, backref="idea_links",
        secondary=Idea.__table__, primaryjoin=(source_id == Idea.id),
        info={'rdf': QuadMapPatternS(None, ASSEMBL.in_conversation)})


_it = Idea.__table__
_ilt = IdeaLink.__table__
Idea.num_children = column_property(
    select([func.count(_ilt.c.id)]).where(
        (_ilt.c.source_id == _it.c.id)
        & (_ilt.c.tombstone_date == None)
        & (_it.c.tombstone_date == None)
        ).correlate_except(_ilt),
    deferred=True)
