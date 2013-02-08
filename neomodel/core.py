from py2neo import neo4j, cypher
from .properties import Property, AliasProperty
from .relationship import RelationshipManager, OUTGOING, RelationshipDefinition
from .exception import (DoesNotExist, RequiredProperty, CypherException,
        ReadOnlyError, NoSuchProperty, PropertyNotIndexed, UniqueProperty)
from .util import camel_to_upper, CustomBatch
from lucenequerybuilder import Q
import types
from urlparse import urlparse
from .signals import hooks
import os


DATABASE_URL = os.environ.get('NEO4J_REST_URL', 'http://localhost:7474/db/data/')


def connection():
    try:
        return connection.db
    except AttributeError:
        url = DATABASE_URL

        u = urlparse(url)
        if u.netloc.find('@') > -1:
            credentials, host = u.netloc.split('@')
            user, password, = credentials.split(':')
            neo4j.authenticate(host, user, password)
            url = ''.join([u.scheme, '://', host, u.path, u.query])

        connection.db = neo4j.GraphDatabaseService(url)
        return connection.db


class CypherMixin(object):
    @property
    def client(self):
        return connection()

    def cypher(self, query, params=None):
        assert hasattr(self, '__node__')
        params = params or {}
        params.update({'self': self.__node__.id})
        try:
            return cypher.execute(self.client, query, params)
        except cypher.CypherError as e:
            message, etype, jtrace = e.args
            raise CypherException(query, params, message, etype, jtrace)


class NodeIndexManager(object):
    def __init__(self, node_class, index_name):
        self.node_class = node_class
        self.name = index_name

    def _check_params(self, params):
        """checked args are indexed and convert aliases"""
        for key in params.keys():
            prop = self.node_class.get_property(key)
            if not prop.is_indexed:
                raise PropertyNotIndexed(key)
            if isinstance(prop, AliasProperty):
                real_key = prop.aliased_to()
                if real_key in params:
                    msg = "Can't alias {0} to {1} in {2}, key {0} exists."
                    raise Exception(msg.format(key, real_key, repr(params)))
                params[real_key] = params[key]
                del params[key]

    def _execute(self, query):
        return self.__index__.query(query)

    def search(self, query=None, **kwargs):
        """ Load multiple nodes via index """
        if not query:
            self._check_params(kwargs)
            query = reduce(lambda x, y: x & y, [Q(k, v) for k, v in kwargs.iteritems()])

        return [self.node_class.inflate(n) for n in self._execute(str(query))]

    def get(self, query=None, **kwargs):
        """ Load single node via index """
        nodes = self.search(query=query, **kwargs)
        if len(nodes) == 1:
            return nodes[0]
        elif len(nodes) > 1:
            raise Exception("Multiple nodes returned from query, expected one")
        else:
            raise self.node_class.DoesNotExist("Can't find node in index matching query")

    @property
    def __index__(self):
        return connection().get_or_create_index(neo4j.Node, self.name)


class StructuredNodeMeta(type):

    NODE_CLASSES = ('StructuredNode', 'ReadOnlyNode')

    def __new__(mcs, name, bases, dct):
        dct.update({'DoesNotExist': type('DoesNotExist', (DoesNotExist,), dct)})
        inst = super(StructuredNodeMeta, mcs).__new__(mcs, name, bases, dct)
        for key, value in dct.iteritems():
            if issubclass(value.__class__, Property):
                value.name = key
                value.owner = inst
                # support for 'magic' properties
                if hasattr(value, 'setup') and hasattr(value.setup, '__call__'):
                    value.setup()
        if inst.__name__ not in StructuredNodeMeta.NODE_CLASSES:
            if '_index_name' in dct:
                name = dct['_index_name']
            inst.index = NodeIndexManager(inst, name)
        return inst


class StructuredNode(CypherMixin):
    """ Base class for nodes requiring declaration of formal structure.

        :ivar __node__: neo4j.Node instance bound to database for this instance
    """

    __metaclass__ = StructuredNodeMeta

    @classmethod
    def get_property(cls, name):
        try:
            node_property = getattr(cls, name)
        except AttributeError:
            raise NoSuchProperty(name, cls)
        if not issubclass(node_property.__class__, Property)\
                or not issubclass(node_property.__class__, AliasProperty):
            NoSuchProperty(name, cls)
        return node_property

    @classmethod
    def category(cls):
        return category_factory(cls)

    @classmethod
    def inflate(cls, node):
        props = {}
        for key, prop in cls._class_properties().iteritems():
            if (issubclass(prop.__class__, Property)
                and not isinstance(prop, AliasProperty)):
                if key in node.__metadata__['data']:
                    props[key] = prop.inflate(node.__metadata__['data'][key], node_id=node.id)
                elif prop.has_default:
                    props[key] = prop.default_value()
                else:
                    props[key] = None

        snode = cls(**props)
        snode.__node__ = node
        return snode

    def __init__(self, *args, **kwargs):
        try:
            super(StructuredNode, self).__init__(*args, **kwargs)
        except TypeError:
            super(StructuredNode, self).__init__()
        self.__node__ = None
        for key, val in self.__class__._class_properties().iteritems():
            if val.__class__ is RelationshipDefinition:
                self.__dict__[key] = val.build_manager(self, key)
            # handle default values
            elif issubclass(val.__class__, Property)\
                    and not isinstance(val, AliasProperty)\
                    and not issubclass(val.__class__, AliasProperty):
                if not key in kwargs or kwargs[key] is None:
                    if val.has_default:
                        kwargs[key] = val.default_value()
        for key, value in kwargs.iteritems():
            if key.startswith("__") and key.endswith("__"):
                pass
            else:
                setattr(self, key, value)

    def __eq__(self, other):
        # equality provider
        return self.__node__ == other.__node__

    def __ne__(self, other):
        # inequality provider
        return self.__node__ != other.__node__

    @classmethod
    def relationship_type(cls):
        return camel_to_upper(cls.__name__)

    @classmethod
    def create(cls, *props):
        category = cls.category()
        batch = CustomBatch(connection(), cls.index.name)
        deflated = [cls.deflate(p) for p in list(props)]
        for p in deflated:
            batch.create_node(p)
        for i in range(0, len(deflated)):
            batch.create_relationship(category.__node__,
                    cls.relationship_type(), i, {"__instance__": True})
            cls._update_indexes(i, deflated[i], batch)
        # build index batch
        results = batch.submit()
        return [cls.inflate(node) for node in results[:len(props)]]

    @classmethod
    def _check_for_conflicts(cls, node, props):
        for key, value in props.iteritems():
            if key in cls._class_properties():
                if cls.get_property(key).unique_index:
                    results = cls.index.__index__.get(key, value)
                    if len(results):
                        if isinstance(node, (int,)): # node ref
                            raise UniqueProperty(key, value, cls.index.name)
                        elif hasattr(node, 'id') and results[0].id != node.id:
                            raise UniqueProperty(key, value, cls.index.name, node)

    @classmethod
    def _update_indexes(cls, node, props, batch):
        # check for conflicts prior to execution
        if batch._graph_db.neo4j_version < (1, 8, 'M07'):
            cls._check_for_conflicts(node, props)

        for key, value in props.iteritems():
            if key in cls._class_properties():
                node_property = cls.get_property(key)
                if node_property.unique_index:
                    try:
                        batch.add_indexed_node_or_fail(cls.index.__index__, key, value, node)
                    except NotImplementedError:
                        batch.get_or_add_indexed_node(cls.index.__index__, key, value, node)
                elif node_property.index:
                    batch.add_indexed_node(cls.index.__index__, key, value, node)
        return batch

    @classmethod
    def _class_properties(cls):
        props = {}
        # get all dict values for inherited classes
        # reverse is done to keep inheritance order
        for scls in reversed(cls.mro()):
            for key, value in scls.__dict__.iteritems():
                props[key] = value
        return props

    @classmethod
    def deflate(cls, node_props, node_id=None):
        """ deflate dict ready to be stored """
        deflated = {}
        for key, prop in cls._class_properties().iteritems():
            if (not isinstance(prop, AliasProperty)
                and issubclass(prop.__class__, Property)):
                if key in node_props and node_props[key] is not None:
                    deflated[key] = prop.deflate(node_props[key], node_id=node_id)
                elif prop.has_default:
                    deflated[key] = prop.deflate(prop.default_value(), node_id=node_id)
                elif prop.required:
                    raise RequiredProperty(key, cls)
        return deflated

    @property
    def __properties__(self):
        node_props = {}
        for key, value in super(StructuredNode, self).__dict__.iteritems():
            if not key.startswith('_')\
                and not isinstance(value, types.MethodType)\
                and not isinstance(value, RelationshipManager)\
                and not isinstance(value, AliasProperty)\
                and value is not None:
                    node_props[key] = value
        return node_props

    @hooks
    def save(self):
        # create or update instance node
        if self.__node__:
            batch = CustomBatch(connection(), self.__class__.index.name, self.__node__.id)
            batch.remove_indexed_node(index=self.__class__.index.__index__, node=self.__node__)
            props = self.deflate(self.__properties__, self.__node__.id)
            batch.set_node_properties(self.__node__, props)
            self.__class__._update_indexes(self.__node__, props, batch)
            batch.submit()
        else:
            self.__node__ = self.__class__.create(self.__properties__)[0].__node__
            if hasattr(self, 'post_create'):
                self.post_create()
        return self

    @hooks
    def delete(self):
        if self.__node__:
            to_delete = self.__node__.get_relationships()
            to_delete.append(self.__node__)
            self.client.delete(*to_delete)
            self.__node__ = None
        else:
            raise Exception("Node has not been saved so cannot be deleted")
        return True


class CategoryNode(CypherMixin):
    def __init__(self, name, *args, **kwargs):
        self.name = name
        super(CategoryNode, self).__init__(*args, **kwargs)


class InstanceManager(RelationshipManager):
    """Manage 'instance' rel of category nodes"""
    def connect(self, node):
        raise Exception("connect not available from category node")

    def disconnect(self, node):
        raise Exception("disconnect not available from category node")


def category_factory(instance_cls):
    """ Retrieve category node by name """
    name = instance_cls.__name__

    if not hasattr(category_factory, 'cache'):
        category_factory.cache = {}

    if not name in category_factory.cache:
        category_index = connection().get_or_create_index(neo4j.Node, 'Category')
        node = category_index.get_or_create('category', name, {'category': name})
        category = CategoryNode(name)
        category.__node__ = node
        category.instance = InstanceManager(OUTGOING, camel_to_upper(name), instance_cls, category)
        category_factory.cache[name] = category
    return category_factory.cache[name]


class ReadOnlyNode(StructuredNode):
    def delete(self):
        raise ReadOnlyError("You cannot delete read-only nodes")

    def save(self):
        raise ReadOnlyError("You cannot save read-only nodes")
