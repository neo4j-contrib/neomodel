from py2neo import neo4j
from py2neo.packages.httpstream import SocketError
from py2neo.exceptions import ClientError
from .exception import DoesNotExist, CypherException
from .util import camel_to_upper, CustomBatch, _legacy_conflict_check
from .properties import Property, PropertyManager, AliasProperty
from .relationship_manager import RelationshipManager, OUTGOING
from .traversal import TraversalSet, Query
from .signals import hooks
from .index import NodeIndexManager
import os
import time
import sys
import logging
logger = logging.getLogger(__name__)

if sys.version_info >= (3, 0):
    from urllib.parse import urlparse
else:
    from urlparse import urlparse  # noqa


DATABASE_URL = os.environ.get('NEO4J_REST_URL', 'http://localhost:7474/db/data/')


def connection():
    if hasattr(connection, 'db'):
        return connection.db

    url = DATABASE_URL
    u = urlparse(url)
    if u.netloc.find('@') > -1:
        credentials, host = u.netloc.split('@')
        user, password, = credentials.split(':')
        neo4j.authenticate(host, user, password)
        url = ''.join([u.scheme, '://', host, u.path, u.query])

    try:
        connection.db = neo4j.GraphDatabaseService(url)
    except SocketError as e:
        raise SocketError("Error connecting to {0} - {1}".format(url, e))

    if connection.db.neo4j_version >= (2, 0):
        raise Exception("Support for neo4j 2.0 is in progress but not supported by this release.")
    if connection.db.neo4j_version < (1, 8):
        raise Exception("Versions of neo4j prior to 1.8 are unsupported.")

    return connection.db


def cypher_query(query, params=None):
    if isinstance(query, Query):
        query = query.__str__()

    try:
        cq = neo4j.CypherQuery(connection(), '')
        start = time.clock()
        r = neo4j.CypherResults(cq._cypher._post({'query': query, 'params': params or {}}))
        end = time.clock()
        results = [list(rr.values) for rr in r.data], list(r.columns)
    except ClientError as e:
        raise CypherException(query, params, e.args[0], e.exception, e.stack_trace)

    if os.environ.get('NEOMODEL_CYPHER_DEBUG', False):
        logger.debug("query: " + query + "\nparams: " + repr(params) + "\ntook: %.2gs\n" % (end - start))

    return results


class CypherMixin(object):
    @property
    def client(self):
        return connection()

    def cypher(self, query, params=None):
        self._pre_action_check('cypher')
        assert self.__node__ is not None
        params = params or {}
        params.update({'self': self.__node__._id})  # TODO: this will break stuff!
        return cypher_query(query, params)


class StructuredNodeMeta(type):
    def __new__(mcs, name, bases, dct):
        dct.update({'DoesNotExist': type('DoesNotExist', (DoesNotExist,), dct)})
        inst = super(StructuredNodeMeta, mcs).__new__(mcs, name, bases, dct)

        if hasattr(inst, '__abstract_node__'):
            delattr(inst, '__abstract_node__')
        else:
            for key, value in dct.items():
                if issubclass(value.__class__, Property):
                    value.name = key
                    value.owner = inst
                    # support for 'magic' properties
                    if hasattr(value, 'setup') and hasattr(value.setup, '__call__'):
                        value.setup()
            if '__index__' in dct or hasattr(inst, '__index__'):
                name = dct['__index__'] if '__index__' in dct else getattr(inst, '__index__')
            inst.index = NodeIndexManager(inst, name)
        return inst


StructuredNodeBase = StructuredNodeMeta('StructuredNodeBase', (PropertyManager,), {})


class StructuredNode(StructuredNodeBase, CypherMixin):
    """ Base class for nodes requiring declaration of formal structure.

        :ivar __node__: neo4j.Node instance bound to database for this instance
    """

    __abstract_node__ = True

    def __init__(self, *args, **kwargs):
        self.__node__ = None
        super(StructuredNode, self).__init__(*args, **kwargs)

    @classmethod
    def category(cls):
        return category_factory(cls)

    def __eq__(self, other):
        if not isinstance(other, (StructuredNode,)):
            raise TypeError("Cannot compare neomodel node with a {}".format(other.__class__.__name__))
        return self.__node__ == other.__node__

    def __ne__(self, other):
        if not isinstance(other, (StructuredNode,)):
            raise TypeError("Cannot compare neomodel node with a {}".format(other.__class__.__name__))
        return self.__node__ != other.__node__

    @hooks
    def save(self):
        # create or update instance node
        if self.__node__ is not None:
            batch = CustomBatch(connection(), self.index.name, self.__node__._id)
            batch.remove_from_index(neo4j.Node, index=self.index.__index__, entity=self.__node__)
            props = self.deflate(self.__properties__, self.__node__._id)
            batch.set_properties(self.__node__, props)
            self._update_indexes(self.__node__, props, batch)
            batch.submit()
        elif hasattr(self, '_is_deleted') and self._is_deleted:
            raise ValueError("{}.save() attempted on deleted node".format(self.__class__.__name__))
        else:
            self.__node__ = self.create(self.__properties__)[0].__node__
            if hasattr(self, 'post_create'):
                self.post_create()
        return self

    def _pre_action_check(self, action):
        if hasattr(self, '_is_deleted') and self._is_deleted:
            raise ValueError("{}.{}() attempted on deleted node".format(self.__class__.__name__, action))
        if self.__node__ is None:
            raise ValueError("{}.{}() attempted on unsaved node".format(self.__class__.__name__, action))

    @hooks
    def delete(self):
        self._pre_action_check('delete')
        self.index.__index__.remove(entity=self.__node__)  # not sure if this is necessary
        self.cypher("START self=node({self}) MATCH (self)-[r]-() DELETE r, self")
        self.__node__ = None
        self._is_deleted = True
        return True

    def traverse(self, rel_manager, *args):
        self._pre_action_check('traverse')
        return TraversalSet(self).traverse(rel_manager, *args)

    def refresh(self):
        self._pre_action_check('refresh')
        """Reload this object from its node in the database"""
        if self.__node__ is not None:
            if self.__node__.exists:
                props = self.inflate(
                    self.client.node(self.__node__._id)).__properties__
                for key, val in props.items():
                    setattr(self, key, val)
            else:
                msg = 'Node %s does not exist in the database anymore'
                raise self.DoesNotExist(msg % self.__node__._id)

    @classmethod
    def create(cls, *props):
        category = cls.category()
        batch = CustomBatch(connection(), cls.index.name)
        deflated = [cls.deflate(p) for p in list(props)]
        # build batch
        for p in deflated:
            batch.create(neo4j.Node.abstract(**p))

        for i in range(0, len(deflated)):
            batch.create(neo4j.Relationship.abstract(category.__node__,
                    cls.relationship_type(), i, __instance__=True))
            cls._update_indexes(i, deflated[i], batch)
        results = batch.submit()
        return [cls.inflate(node) for node in results[:len(props)]]

    @classmethod
    def inflate(cls, node):
        props = {}
        for key, prop in cls._class_properties().items():
            if (issubclass(prop.__class__, Property)
                    and not isinstance(prop, AliasProperty)):
                if key in node.__metadata__['data']:
                    props[key] = prop.inflate(node.__metadata__['data'][key], node)
                elif prop.has_default:
                    props[key] = prop.default_value()
                else:
                    props[key] = None

        snode = cls(**props)
        snode.__node__ = node
        return snode

    @classmethod
    def relationship_type(cls):
        return camel_to_upper(cls.__name__)

    @classmethod
    def _update_indexes(cls, node, props, batch):
        # check for conflicts prior to execution
        if batch._graph_db.neo4j_version < (1, 9):
            _legacy_conflict_check(cls, node, props)

        for key, value in props.items():
            if key in cls._class_properties():
                node_property = cls.get_property(key)
                if node_property.unique_index:
                    try:
                        batch.add_to_index_or_fail(neo4j.Node, cls.index.__index__, key, value, node)
                    except NotImplementedError:
                        batch.get_or_add_to_index(neo4j.Node, cls.index.__index__, key, value, node)
                elif node_property.index:
                    batch.add_to_index(neo4j.Node, cls.index.__index__, key, value, node)
        return batch


class CategoryNode(CypherMixin):
    def __init__(self, name):
        self.name = name

    def traverse(self, rel):
        return TraversalSet(self).traverse(rel)

    def _pre_action_check(self, action):
        pass


class InstanceManager(RelationshipManager):
    """Manage 'instance' rel of category nodes"""
    def connect(self, node):
        raise Exception("connect not available from category node")

    def disconnect(self, node):
        raise Exception("disconnect not available from category node")


def category_factory(instance_cls):
    """ Retrieve category node by name """
    name = instance_cls.__name__
    category_index = connection().get_or_create_index(neo4j.Node, 'Category')
    category = CategoryNode(name)
    category.__node__ = category_index.get_or_create('category', name, {'category': name})
    rel_type = camel_to_upper(instance_cls.__name__)
    category.instance = InstanceManager({
        'direction': OUTGOING,
        'relation_type': rel_type,
        'target_map': {rel_type: instance_cls},
    }, category)
    category.instance.name = 'instance'
    return category
