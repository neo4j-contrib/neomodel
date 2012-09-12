from py2neo import neo4j
from lucenequerybuilder import Q
import sys
import os


class NeoDB(object):
    """ Manage and cache connections to neo4j """

    def __init__(self):
        self.client = neo4j.GraphDatabaseService(os.environ.get('NEO4J_URL'))
        self.category_cache = {}
        self.index_cache = {}

    def index(self, name):
        """ Retrieve index by name """
        if name not in self.index_cache:
            index = self.client.get_or_create_index(neo4j.Node, name)
            self.index_cache[name] = index

        return self.index_cache[name]

    def category(self, name):
        """ Rerieve category node by name """
        if name not in self.category_cache:
            try:
                category = self.index('Category').get('category', name)[0]
            except IndexError:
                raise Exception("Category node '" + name + "' doesn't exist in category index")
            self.category_cache[name] = category

        return self.category_cache[name]


class NeoNodeMeta(type):
    def __new__(cls, name, bases, dct):
        if name != 'NeoNode':
            db = NeoDB()
            dct['db'] = db
            dct['index'] = db.index(name)
            dct['category_node'] = db.category(name)
        return super(NeoNodeMeta, cls).__new__(cls, name, bases, dct)


class NeoNode(object):
    """ Base class for nodes requiring formal declaration """

    __metaclass__ = NeoNodeMeta

    @classmethod
    def load_many(cls, query=None, **kwargs):
        """ Load multiple nodes via index """
        for k, v in kwargs.iteritems():
            p = cls.get_property(k)
            if not p:
                raise NoSuchProperty(k)
            if not p.is_indexed:
                raise PropertyNotIndexed(k)
            p.validate(v)

        if not query:
            query = reduce(lambda x, y: x & y, [Q(k, v) for k, v in kwargs.iteritems()])

        result = cls.index.query(query)
        nodes = []

        for node in result:
            properties = node.get_properties()
            neonode = cls(**properties)
            neonode._db = cls.db
            neonode._node = node
            nodes.append(neonode)
        return nodes

    @classmethod
    def load(cls, query=None, **kwargs):
        """ Load single node via index """
        nodes = cls.load_many(query, **kwargs)
        if len(nodes) == 1:
            return nodes[0]
        elif len(nodes) > 1:
            raise Exception("Multiple nodes returned from query, expected one")
        else:
            raise Exception("No nodes found")

    @classmethod
    def get_property(cls, name):
        node_property = getattr(cls, name)
        if not node_property or not issubclass(node_property.__class__, Property):
            Exception(name + " is not a Property of " + cls.__name__)
        return node_property

    def __init__(self, *args, **kwargs):
        self._validate_args(kwargs)
        self._node = None

    def __setattr__(self, key, value):
        if key.startswith('_'):
            self.__dict__[key] = value
            return
        prop = self.__class__.get_property(key)
        if prop.validate(value):
            self.__dict__[key] = value

    @property
    def properties(self):
        """ Return properties and values of a node """
        props = {}
        for key, value in self.__dict__.iteritems():
            if not key.startswith('_'):
                props[key] = value
        return props

    def _validate_args(self, props):
        """ Validate dict and set node properties """
        for key, value in props.iteritems():
            if key in self.__class__.__dict__:
                node_property = self.__class__.get_property(key)
                node_property.validate(value)
                self.__dict__[key] = value
            else:
                raise NoSuchProperty(key)

    def _create(self, props):
        # TODO make this single atomic operation
        relation_name = self.__class__.__name__.upper()
        self._node, rel = self.__class__.db.client.create(props,
                (self.__class__.category_node, relation_name, 0))
        if not self._node:
            Exception('Failed to create new ' + self.__class__.name)

        # Update indexes
        try:
            self._update_index(props)
        except Exception:
            exc_info = sys.exc_info()
            self.delete()
            raise exc_info[1], None, exc_info[2]

    def _update_index(self, props):
        for key, value in props.iteritems():
            node_property = self.__class__.get_property(key)
            if node_property.unique_index:
                if not self.__class__.index.add_if_none(key, value, self._node):
                    raise NotUnique('{0}: {1} exists in unique index {2}'
                            .format(key, value, self.__class__.__name__))
            elif node_property.index:
                self.__class__.index.add(key, value, self._node)

    def save(self):
        if self._node:
            self._node.set_properties(self.properties)
            self.__class__.index.remove_node(self._node)
            self._update_index(self.properties)
        else:
            self._create(self.properties)
        return self

    def delete(self):
        if self._node:
            for r in self._node.get_relationships():
                r.delete()
            self._node.delete()
            self._node = None
        else:
            raise Exception("Node has not been saved so cannot be deleted")
        return True


# TODO handle 'blank' correctly
class Property(object):
    def __init__(self, unique_index=False, index=False, blank=False):
        if unique_index and index:
            raise Exception("unique_index and index are mutually exclusive")
        if unique_index and blank:
            raise Exception("uniquely indexed properties cannot also be blank")
        self.unique_index = unique_index
        self.index = index

    @property
    def is_indexed(self):
        return self.unique_index or self.index


class StringProperty(Property):
    def validate(self, value):
        if isinstance(value, (str, unicode)):
            return True
        else:
            raise TypeError("Object of type str expected got " + str(value))


class IntegerProperty(Property):
    def validate(self, value):
        if isinstance(value, (int, long)):
            return True
        else:
            raise TypeError("Object of type int or long expected")


class NoSuchProperty(Exception):
    pass


class PropertyNotIndexed(Exception):
    pass


class NotUnique(Exception):
    pass
