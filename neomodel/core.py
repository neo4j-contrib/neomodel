from py2neo import neo4j
from .indexbatch import IndexBatch
from .properties import StringProperty, Property
from .relationship import (RelationshipInstaller, RelationshipManager,
        RelationshipDefinition, OUTGOING)
from lucenequerybuilder import Q
import types
import sys
import os


class NeoDB(object):
    """ Manage and cache connections to neo4j """

    def __init__(self, graph_db):
        self.client = graph_db
        self.category_cache = {}

    def category(self, name):
        """ Retrieve category node by name """
        category_index = self.client.get_or_create_index(neo4j.Node, 'Category')

        if name not in self.category_cache:
            category = category_index.get_or_create('category', name, {'category': name})
            self.category_cache[name] = category

        return self.category_cache[name]


def connection_adapter():
    try:
        return connection_adapter.db
    except AttributeError:
        url = os.environ.get('NEO4J_URL', 'http://localhost:7474/db/data/')
        graph_db = neo4j.GraphDatabaseService(url)
        connection_adapter.db = NeoDB(graph_db)
        return connection_adapter.db


class NodeIndexManager(object):
    def __init__(self, node_class, index_name, client):
        self.node_class = node_class
        self.name = index_name
        self._cached_index = None
        self.client = client

    @property
    def _index(self):
        if not self._cached_index:
            self._cached_index = self.client.get_or_create_index(neo4j.Node, self.name)

        return self._cached_index

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


class StructuredNodeMeta(type):
    def __new__(cls, name, bases, dct):
        cls = super(StructuredNodeMeta, cls).__new__(cls, name, bases, dct)
        if cls.__name__ != 'StructuredNode' or cls.__name__ != 'ReadOnlyNode':
            db = connection_adapter()
            if '_index_name' in dct:
                name = dct['_index_name']
            cls.index = NodeIndexManager(cls, name, db.client)
        return cls


class StructuredNode(RelationshipInstaller):
    """ Base class for nodes requiring formal declaration """

    __metaclass__ = StructuredNodeMeta

    @classmethod
    def get_property(cls, name):
        node_property = getattr(cls, name)
        if not node_property or not issubclass(node_property.__class__, Property):
            Exception(name + " is not a Property of " + cls.__name__)
        return node_property

    @classmethod
    def category(cls):
        if not hasattr(cls, '_category'):
            node = connection_adapter().category(cls.__name__)
            rel = RelationshipDefinition(cls.__name__.upper(), cls, OUTGOING, CategoryInstanceRM)
            category_node_class = type(cls.__name__ + 'CategoryNode', (CategoryNode,),
                    dict(instance=rel))
            cls._category = category_node_class(node)
            cls._category._node = node
        return cls._category

    def __init__(self, *args, **kwargs):
        self._validate_args(kwargs)
        self._node = None
        self._db = connection_adapter()
        self._type = self.__class__.__name__
        self._index = self.client.get_or_create_index(neo4j.Node, self._type)

        super(StructuredNode, self).__init__(*args, **kwargs)

    def __setattr__(self, key, value):
        if key.startswith('_'):
            self.__dict__[key] = value
            return
        try:
            prop = self.__class__.get_property(key)
        except NoSuchProperty:
            self.__dict__[key] = value
        else:
            if prop.validate(value):
                self.__dict__[key] = value

    @property
    def client(self):
        return self._db.client

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

    def _validate_args(self, props):
        """ Validate dict and set node properties """
        for cls in self.__class__.mro():
            if cls.__name__ == 'StructuredNode' or cls.__name__ == 'ReadOnlyNode':
                break
            for key, node_property in cls.__dict__.iteritems():
                if key in props:
                    value = props[key]
                else:
                    value = None
                if isinstance(node_property, Property):
                    node_property.validate(value)
                self.__dict__[key] = value

    def _create(self, props):
        relation_name = self._type.upper()
        self._node, rel = self.client.create(props,
                (self._db.category(self._type), relation_name, 0))
        if not self._node:
            Exception('Failed to create new ' + self._type)

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
            if 200 in [r.status for r in batch.submit()]:
                raise NotUnique('A supplied value is not unique' + r.uri)

    def save(self):
        if self._node:
            self._node.set_properties(self.properties)
            self._index.remove(entity=self._node)
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


class CategoryNode(RelationshipInstaller):
    category = StringProperty()

    def __init__(self, *args, **kwargs):
        self._db = connection_adapter()
        super(CategoryNode, self).__init__(*args, **kwargs)


class CategoryInstanceRM(RelationshipManager):
    def connect(self):
        raise Exception("connect not available from category node")

    def disconnect(self):
        raise Exception("disconnect not available from category node")


class ReadOnlyNode(StructuredNode):
    def delete():
        raise ReadOnlyError("You cannot delete read-only nodes")

    def update():
        raise ReadOnlyError("You cannot update read-only nodes")

    def save():
        raise ReadOnlyError("You cannot save read-only nodes")

    def __setattr__(self, key, value):
        if key.startswith('_'):
            self.__dict__[key] = value
            return
        raise ReadOnlyError("You cannot save properties on a read-only node")


class ReadOnlyError(Exception):
    pass


class NoSuchProperty(Exception):
    pass


class PropertyNotIndexed(Exception):
    pass


class NotUnique(Exception):
    pass


class DoesNotExist(Exception):
    pass
