from py2neo import neo4j, cypher, rest
from .properties import Property
from .relationship import RelationshipManager, OUTGOING, RelationshipDefinition
from .exception import (NotUnique, DoesNotExist, RequiredProperty, CypherException,
        ReadOnlyError, NoSuchProperty, PropertyNotIndexed)
from lucenequerybuilder import Q
import types
import sys
from urlparse import urlparse
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


class Client(object):
    @property
    def client(self):
        return connection()


class NodeIndexManager(Client):
    def __init__(self, node_class, index_name):
        self.node_class = node_class
        self.name = index_name

    def search(self, query=None, **kwargs):
        """ Load multiple nodes via index """
        for k, v in kwargs.iteritems():
            p = self.node_class.get_property(k)
            if not p:
                raise NoSuchProperty(k)
            if not p.is_indexed:
                raise PropertyNotIndexed(k)
            p.validate(v)

        if not query:
            query = reduce(lambda x, y: x & y, [Q(k, v) for k, v in kwargs.iteritems()])

        results = self._index.query(str(query))
        props = self.client.get_properties(*results)
        nodes = []

        for node, properties in dict(zip(results, props)).iteritems():
            neonode = self.node_class(**properties)
            neonode.__node__ = node
            nodes.append(neonode)
        return nodes

    def get(self, query=None, **kwargs):
        """ Load single node via index """
        nodes = self.search(query, **kwargs)
        if len(nodes) == 1:
            return nodes[0]
        elif len(nodes) > 1:
            raise Exception("Multiple nodes returned from query, expected one")
        else:
            raise self.node_class.DoesNotExist("Can't find node in index matching query")

    @property
    def _index(self):
        return self.client.get_or_create_index(neo4j.Node, self.name)


class CypherMixin(Client):
    def cypher(self, query, params={}):
        assert hasattr(self, '__node__')
        params.update({'self': self.__node__.id})
        try:
            return cypher.execute(self.client, query, params)
        except cypher.CypherError as e:
            message, etype, jtrace = e.args
            raise CypherException(query, params, message, etype, jtrace)

    def start_cypher(self, query, params={}):
        print "DEPRECATION 19/10/2012: start_cypher not longer supported, please use cypher"
        start = "START a=node({self}) "
        return self.cypher(start + query, params)


class StructuredNodeMeta(type):
    def __new__(cls, name, bases, dct):
        dct.update({'DoesNotExist': type('DoesNotExist', (DoesNotExist,), dct)})
        cls = super(StructuredNodeMeta, cls).__new__(cls, name, bases, dct)
        if cls.__name__ not in ['StructuredNode', 'ReadOnlyNode']:
            if '_index_name' in dct:
                name = dct['_index_name']
            cls.index = NodeIndexManager(cls, name)
        return cls


class StructuredNode(CypherMixin):
    """ Base class for nodes requiring formal declaration """

    __metaclass__ = StructuredNodeMeta

    @classmethod
    def get_property(cls, name):
        try:
            node_property = getattr(cls, name)
        except AttributeError:
            raise NoSuchProperty
        if node_property and not issubclass(node_property.__class__, Property):
            NoSuchProperty(name + " is not a Property of " + cls.__name__)
        return node_property

    @classmethod
    def category(cls):
        return category_factory(cls)

    def __init__(self, *args, **kwargs):
        self.__node__ = None

        for key, val in self.__class__.__dict__.iteritems():
            if val.__class__ is RelationshipDefinition:
                self.__dict__[key] = val.build_manager(self, key)
            if issubclass(val.__class__, Property):
                    self.__dict__[key] = None
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

    def _validate(self):
        node_props = self.properties
        for key, prop in self.__class__.__dict__.iteritems():
            if issubclass(prop.__class__, Property):
                if key in node_props:
                    prop.validate(node_props[key])
                elif prop.required:
                    raise RequiredProperty(key + " on " + self.__class__.__name__)

    @property
    def properties(self):
        """ Return properties and values of a node """
        props = {}
        for key, value in self.__dict__.iteritems():
            if not key.startswith('_')\
                and not isinstance(value, types.MethodType)\
                and not isinstance(value, RelationshipManager)\
                and value != None:
                    props[key] = value

        return props

    def _create(self, props):
        relation_name = self.__class__.__name__.upper()
        self.__node__, rel = self.client.create(props,
                (category_factory(self.__class__).__node__, relation_name, 0))
        if not self.__node__:
            Exception('Failed to create new ' + self.__class__.__name__)

        # Update indexes
        try:
            self._update_index(props)
        except Exception:
            exc_info = sys.exc_info()
            self.delete()
            raise exc_info[1], None, exc_info[2]

    def _update_index(self, props):
        for cls in self.__class__.mro():
            if cls.__name__ == 'StructuredNode' or cls.__name__ == 'ReadOnlyNode':
                break
            batch = neo4j.WriteBatch(self.client)
            for key, value in props.iteritems():
                if key in cls.__dict__.keys():
                    node_property = cls.get_property(key)
                    if node_property.unique_index:
                        try:
                            batch.add_indexed_node_or_fail(cls.index._index, key, value, self.__node__)
                        except NotImplementedError:
                            batch.get_or_add_indexed_node(cls.index._index, key, value, self.__node__)
                    elif node_property.index:
                        batch.add_indexed_node(cls.index._index, key, value, self.__node__)
            try:
                for r in batch._submit():
                    if r.status == 200:
                        raise NotUnique('A supplied value is not unique' + r.uri)
            except rest.ResourceConflict as r:
                raise NotUnique('A supplied value is not unique' + r.uri)

    def save(self):
        self._validate()
        if self.__node__:
            self.__node__.set_properties(self.properties)
            self.__class__.index._index.remove(entity=self.__node__)
            self._update_index(self.properties)
        else:
            self._create(self.properties)
        return self

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
            category.instance = InstanceManager(OUTGOING, name.upper(), instance_cls, category)
            category_factory.cache[name] = category
        return category_factory.cache[name]


class ReadOnlyNode(StructuredNode):
    def delete(self):
        raise ReadOnlyError("You cannot delete read-only nodes")

    def update(self):
        raise ReadOnlyError("You cannot update read-only nodes")

    def save(self):
        raise ReadOnlyError("You cannot save read-only nodes")
