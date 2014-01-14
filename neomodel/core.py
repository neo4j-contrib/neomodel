from .util import neo4j, cypher_query
from py2neo.packages.httpstream import SocketError
from .exception import DoesNotExist
from .properties import Property, PropertyManager
from .traversal import TraversalSet
from .signals import hooks
from types import MethodType
import os
import sys

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


def install_labels(cls):
    # TODO when to execute this?
    for key, prop in cls.defined_properties(aliases=False, rels=False).items():
        if prop.index:
            cypher_query(connection(), "CREATE INDEX on :{}({}); ".format(cls.__label__, key))
        elif prop.unique_index:
            cypher_query(connection(), "CREATE CONSTRAINT on (n:{}) ASSERT n.{} IS UNIQUE; ".format(
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


NodeBase = NodeMeta('NodeBase', (PropertyManager,), {'__abstract_node__': True})


def _traverse(self, rel_manager, *args):
    self._pre_action_check('traverse')
    return TraversalSet(connection(), self).traverse(rel_manager, *args)


class StructuredNode(NodeBase):
    __abstract_node__ = True

    def __init__(self, *args, **kwargs):
        for key, val in self.defined_properties(aliases=False, properties=False).items():
            self.__dict__[key] = val.build_manager(self, key)

        # install traverse an instance method
        # http://stackoverflow.com/questions/861055/
        self.traverse = MethodType(_traverse, self, self.__class__)
        super(StructuredNode, self).__init__(*args, **kwargs)

    def __eq__(self, other):
        if not isinstance(other, (StructuredNode,)):
            raise TypeError("Cannot compare neomodel node with a " + other.__class__.__name__)
        return self._id == other._id

    def __ne__(self, other):
        if not isinstance(other, (StructuredNode,)):
            raise TypeError("Cannot compare neomodel node with a " + other.__class__.__name__)
        return self._id != other._id

    def cypher(self, query, params=None):
        self._pre_action_check('cypher')
        params = params or {}
        params.update({'self': self._id})
        return cypher_query(connection(), query, params)

    @classmethod
    def inherited_labels(cls):
        return [scls.__label__ for scls in cls.mro()
                if hasattr(scls, '__label__') and not hasattr(scls, '__abstract_node__')]

    @classmethod
    def category(cls):
        return FakeCategory(cls)

    @hooks
    def save(self):
        # create or update instance node
        if hasattr(self, '_id'):
            # update
            query = "START self=node({self})\n"
            query += "\n".join(["SET self.{} = {{{}}}".format(key, key) + "\n"
                for key in self.__properties__.keys()])
            for label in self.inherited_labels():
                query += "SET self:`{}`\n".format(label)
            params = self.deflate(self.__properties__, self)
            self.cypher(query, params)
        # TODO renamed _deleted
        elif hasattr(self, '_is_deleted') and self._is_deleted:
            raise ValueError("{}.save() attempted on deleted node".format(self.__class__.__name__))
        else: # create
            self._id = self.create(self.__properties__)[0]._id
        return self

    def _pre_action_check(self, action):
        if hasattr(self, '_is_deleted') and self._is_deleted:
            raise ValueError("{}.{}() attempted on deleted node".format(self.__class__.__name__, action))
        if not hasattr(self, '_id'):
            raise ValueError("{}.{}() attempted on unsaved node".format(self.__class__.__name__, action))

    @hooks
    def delete(self):
        self._pre_action_check('delete')
        self.cypher("START self=node({self}) DELETE self")
        del self.__dict__['_id']
        self._is_deleted = True
        return True

    @classmethod
    def traverse(cls):
        return TraversalSet(connection(), cls)

    def refresh(self):
        """Reload this object from its node id in the database"""
        self._pre_action_check('refresh')
        if hasattr(self, '_id'):
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

        results, meta = cypher_query(connection(), query, params)

        if hasattr(cls, 'post_create'):
            for node in results:
                node.post_create()

        return [cls.inflate(node) for node in results[0]]

    @classmethod
    def inflate(cls, node):
        props = {}
        for key, prop in cls.defined_properties(aliases=False, rels=False).items():
            if key in node._properties:
                props[key] = prop.inflate(node._properties[key], node)
            elif prop.has_default:
                props[key] = prop.default_value()
            else:
                props[key] = None

        snode = cls(**props)
        snode._id = node._id
        return snode


class FakeCategory(object):
    """
    Category nodes are no longer required with the introduction of labels.
    This class behaves like the old category nodes used in earlier version of neomodel
    but uses labels under the hood calling the traversal api.
    """
    def __init__(self, cls):
        self.instance = FakeInstanceRel(cls)

    def cypher(self, *args, **kwargs):
        raise NotImplemented("cypher method on category nodes no longer supported")


class FakeInstanceRel(object):
    """
    Fake rel manager for our fake category node
    """
    def __init__(self, cls):
        self.node_class = cls

    def _new_traversal(self):
        return TraversalSet(connection(), self.node_class)

    def __len__(self):
        return len(self._new_traversal())

    def __bool__(self):
        return len(self) > 0

    def __nonzero__(self):
        return len(self) > 0

    def count(self):
        return self.__len__()

    def all(self):
        return self._new_traversal().run()

    def search(self, **kwargs):
        t = self._new_traversal()
        for field, value in kwargs.items():
            t.where(field, '=', value)
        return t.run()

    def get(self, **kwargs):
        result = self.search(**kwargs)
        if len(result) == 1:
            return result[0]
        if len(result) > 1:
            raise Exception("Multiple items returned, use search?")
        if not result:
            raise DoesNotExist("No items exist for the specified arguments")
