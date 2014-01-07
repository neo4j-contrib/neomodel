from py2neo import neo4j
from py2neo.packages.httpstream import SocketError
from py2neo.exceptions import ClientError
from .exception import DoesNotExist, CypherException, UniqueProperty
from .properties import Property, PropertyManager
from .traversal import TraversalSet, Query
from .signals import hooks
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

    if connection.db.neo4j_version < (2, 0):
        raise Exception("Support for neo4j versions prior to 2.0 are "
                + "supported by the 0.x series releases of neomodel")

    return connection.db


def cypher_query(query, params=None, handle_unique=True):
    if isinstance(query, Query):
        query = query.__str__()

    try:
        cq = neo4j.CypherQuery(connection(), '')
        start = time.clock()
        r = neo4j.CypherResults(cq._cypher._post({'query': query, 'params': params or {}}))
        end = time.clock()
        results = [list(r.values) for r in r.data], list(r.columns)
    except ClientError as e:
        if (handle_unique and e.exception == 'CypherExecutionException' and
                " already exists with label " in e.message and e.message.startswith('Node ')):
            raise UniqueProperty(e.message)

        raise CypherException(query, params, e.message, e.exception, e.stack_trace)

    if os.environ.get('NEOMODEL_CYPHER_DEBUG', False):
        logger.debug("query: " + query + "\nparams: " + repr(params) + "\ntook: %.2gs\n" % (end - start))

    return results


def install_labels(cls):
    for key, prop in cls.defined_properties(aliases=False, rels=False).items():
        if prop.index:
            cypher_query("CREATE INDEX on :{}({}); ".format(cls.__label__, key))
        elif prop.unique_index:
            cypher_query("CREATE CONSTRAINT on (n:{}) ASSERT n.{} IS UNIQUE; ".format(
                    cls.__label__, key))


class NodeMeta(type):
    def __new__(mcs, name, bases, dct):
        dct.update({'DoesNotExist': type('DoesNotExist', (DoesNotExist,), dct)})
        inst = super(NodeMeta, mcs).__new__(mcs, name, bases, dct)

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
            # TODO: prevent __label__ from being inheritted
            if '__label__' in dct:
                inst.__label__ = dct['__label__']
            else:
                inst.__label__ = inst.__name__

            install_labels(inst)
            from .index import NodeIndexManager
            inst.index = NodeIndexManager(inst, inst.__label__)
        return inst


NodeBase = NodeMeta('NodeBase', (PropertyManager,), {})


class StructuredNode(NodeBase):

    __abstract_node__ = True

    def __init__(self, *args, **kwargs):
        self.__node__ = None
        super(StructuredNode, self).__init__(*args, **kwargs)

    def __eq__(self, other):
        if not isinstance(other, (StructuredNode,)):
            raise TypeError("Cannot compare neomodel node with a " + other.__class__.__name__)
        return self.__node__._id == other.__node__._id

    def __ne__(self, other):
        if not isinstance(other, (StructuredNode,)):
            raise TypeError("Cannot compare neomodel node with a " + other.__class__.__name__)
        return self.__node__ != other.__node__

    def cypher(self, query, params=None):
        self._pre_action_check('cypher')
        params = params or {}
        params.update({'self': self.__node__._id})
        return cypher_query(query, params)

    def labels(self):
        pass # todo

    @classmethod
    def inherited_labels(cls):
        return [scls.__label__ for scls in cls.mro() if hasattr(scls, '__label__')]

    @hooks
    def save(self):
        # create or update instance node
        if self.__node__ is not None:
            # update
            query = "START self=node({self})\n"
            query += "\n".join(["SET self.{} = {{{}}}".format(key, key) + "\n"
                for key in self.__properties__.keys()])
            for label in self.inherited_labels():
                query += "SET self:`{}`\n".format(label)
            params = self.deflate(self.__properties__, self)
            self.cypher(query, params)

        elif hasattr(self, '_is_deleted') and self._is_deleted:
            raise ValueError("{}.save() attempted on deleted node".format(self.__class__.__name__))
        else:
            # create
            self.__node__ = self.create(self.__properties__)[0].__node__
        return self

    def _pre_action_check(self, action):
        if hasattr(self, '_is_deleted') and self._is_deleted:
            raise ValueError("{}.{}() attempted on deleted node".format(self.__class__.__name__, action))
        if self.__node__ is None:
            raise ValueError("{}.{}() attempted on unsaved node".format(self.__class__.__name__, action))

    @hooks
    def delete(self):
        self._pre_action_check('delete')
        self.cypher("START self=node({self}) DELETE self")
        self.__node__ = None
        self._is_deleted = True
        return True

    def traverse(self, rel_manager, *args):
        assert False
        self._pre_action_check('traverse')
        return TraversalSet(self).traverse(rel_manager, *args)

    def refresh(self):
        """Reload this object from its node id in the database"""
        self._pre_action_check('refresh')
        if self.__node__ is not None:
            node = self.inflate(self.cypher("START n=node({self}) RETURN n")[0][0][0])
            for key, val in node.__properties__.items():
                setattr(self, key, val)

    @classmethod
    def create(cls, *props):
        query = ""
        deflated = [cls.deflate(p) for p in list(props)]
        params = {}
        for i in range(0, len(deflated)):
            props = ", ".join(["{}: {{n{}_{}}}".format(key, i, key)
                    for key, value in deflated[i].items()])
            query += "CREATE (n{} {{{}}})\n".format(i, props)

            for label in cls.inherited_labels():
                query += "SET n{}:`{}`\n".format(i, label)

            for key, value in deflated[i].items():
                params["n{}_{}".format(i, key)] = value

        query += "RETURN "
        query += ", ".join(["n" + str(i) for i in range(0, len(deflated))])

        results, meta = cypher_query(query, params)

        if hasattr(cls, 'post_create'):
            for node in results:
                node.post_create()

        return [cls.inflate(node) for node in results[0]]

    @classmethod
    def inflate(cls, node):
        props = {}
        for key, prop in cls.defined_properties(aliases=False, rels=False).items():
                if key in node.__metadata__['data']:
                    props[key] = prop.inflate(node.__metadata__['data'][key], node)
                elif prop.has_default:
                    props[key] = prop.default_value()
                else:
                    props[key] = None

        snode = cls(**props)
        snode.__node__ = node
        return snode
