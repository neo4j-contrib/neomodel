from py2neo import neo4j, cypher
from .indexbatch import IndexBatch
from .properties import Property
from .relationship import RelationshipInstaller, RelationshipManager, OUTGOING
from .exception import NotUnique, DoesNotExist
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
            neonode._node = node
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
            raise DoesNotExist("Can't find node in index matching query")

    @property
    def _index(self):
        return self.client.get_or_create_index(neo4j.Node, self.name)


class StructuredNodeMeta(type):
    def __new__(cls, name, bases, dct):
        cls = super(StructuredNodeMeta, cls).__new__(cls, name, bases, dct)
        if cls.__name__ != 'StructuredNode' or cls.__name__ != 'ReadOnlyNode':
            if '_index_name' in dct:
                name = dct['_index_name']
            cls.index = NodeIndexManager(cls, name)
        return cls


class CypherMixin(Client):
    def cypher(self, query, params=None):
        return cypher.execute(self.client, query, params)

    def start_cypher(self, query, params=None):
        start = "START a=node({:d}) ".format(self._node.id)
        return self.cypher(start + query, params)


class StructuredNode(RelationshipInstaller, CypherMixin):
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
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

        # set missing props to none.
        for key, prop in self.__class__.__dict__.iteritems():
            if key.startswith('_'):
                continue
            if issubclass(prop.__class__, Property) and not key in self.__dict__:
                super(StructuredNode, self).__setattr__(key, None)
        self._node = None
        self._type = self.__class__.__name__

        super(StructuredNode, self).__init__(*args, **kwargs)

    def __setattr__(self, key, value):
        if key.startswith('_'):
            return super(StructuredNode, self).__setattr__(key, value)
        try:
            prop = self.__class__.get_property(key)
        except NoSuchProperty:
            super(StructuredNode, self).__setattr__(key, value)
        else:
            if hasattr(prop, 'validate') and callable(prop.validate):
                prop.validate(value)
            super(StructuredNode, self).__setattr__(key, value)

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
        self._node, rel = self.client.create(props,
                (category_factory(self.__class__)._node, relation_name, 0))
        if not self._node:
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
            batch = IndexBatch(cls.index._index)
            for key, value in props.iteritems():
                if key in cls.__dict__.keys():
                    node_property = cls.get_property(key)
                    if node_property.unique_index:
                        batch.add_if_none(key, value, self._node)
                    elif node_property.index:
                        batch.add(key, value, self._node)
            for r in batch.submit():
                if r.status == 200:
                    raise NotUnique('A supplied value is not unique' + r.uri)

    def save(self):
        if self._node:
            self._node.set_properties(self.properties)
            self.__class__.index._index.remove(entity=self._node)
            self._update_index(self.properties)
        else:
            self._create(self.properties)
        return self

    def delete(self):
        if self._node:
            to_delete = self._node.get_relationships()
            to_delete.append(self._node)
            self.client.delete(*to_delete)
            self._node = None
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
            category._node = node
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


class ReadOnlyError(Exception):
    pass


class NoSuchProperty(Exception):
    pass


class PropertyNotIndexed(Exception):
    pass
