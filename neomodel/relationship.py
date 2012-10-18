from py2neo import neo4j
import sys
from .exception import DoesNotExist

OUTGOING = neo4j.Direction.OUTGOING
INCOMING = neo4j.Direction.INCOMING
EITHER = neo4j.Direction.EITHER


def _related(direction):
    if direction == OUTGOING:
        return '-[{0}]->'
    elif direction == INCOMING:
        return '<-[{0}]-'
    else:
        return '-[{0}]-'


def _properties(ident, **kwargs):
    props = [ident + '.' + k + ' = {' + k + '}' for k in kwargs]
    return '(' + ', '.join(props) + ')'


def _wrap(unwrapped, props, cls):
        nodes = []
        for node, properties in zip(unwrapped, props):
            wrapped_node = cls(**(properties))
            wrapped_node.__node__ = node
            nodes.append(wrapped_node)
        return nodes


class RelationshipManager(object):
    def __init__(self, direction, relation_type, node_classes, origin):
        self.direction = direction
        self.relation_type = relation_type
        if isinstance(node_classes, list):
            self.node_classes = node_classes
            self.class_map = dict(zip([c.__name__.upper() for c in node_classes],
                node_classes))
        else:
            self.node_class = node_classes
        self.origin = origin

    @property
    def client(self):
        return self.origin.client

    def all(self):
        if hasattr(self, 'node_classes'):
            return self._all_multi_class()
        else:
            return self._all_single_class()

    def _wrap_multi_class_resultset(self, results):
        """With resultset containing [node,rel] pairs
        wrap each node in correct neomodel class based on rel.type"""
        unwrapped = [row[0] for row in results]
        classes = [self.class_map[row[1].type] for row in results]
        props = self.client.get_properties(*unwrapped)
        nodes = []
        for node, cls, prop in zip(unwrapped, classes, props):
            wrapped_node = cls(**prop)
            wrapped_node.__node__ = node
            nodes.append(wrapped_node)
        return nodes

    def _all_multi_class(self):
        cat_types = "|".join([c.__name__.upper() for c in self.node_classes])
        query = "MATCH (a)" + _related(self.direction).format(self.relation_type)
        query += "(x)<-[r:{0}]-() RETURN x, r".format(cat_types)
        results = self.origin.start_cypher(query)[0]
        return self._wrap_multi_class_resultset(results)

    def _all_single_class(self):
        related_nodes = self.origin.__node__.get_related_nodes(self.direction, self.relation_type)
        if not related_nodes:
            return []
        props = self.client.get_properties(*related_nodes)
        return _wrap(related_nodes, props, self.node_class)

    def get(self, **kwargs):
        result = self.search(**kwargs)
        if len(result) == 1:
            return result[0]
        if len(result) > 1:
            raise Exception("Multiple items returned")
        if not result:
            raise DoesNotExist("No items exist for the specified arguments")

    def search(self, **kwargs):
        if not kwargs:
            if hasattr(self, 'node_classes'):
                return self._all_multi_class()
            else:
                return self._all_single_class()

        if hasattr(self, 'node_classes'):
            return self._search_multi_class(**kwargs)
        else:
            return self._search_single_class(**kwargs)

    def _search_single_class(self, **kwargs):
        query = "MATCH (a)"
        query += _related(self.direction).format(self.relation_type)
        query += "(b) WHERE " + _properties('b', **kwargs)
        query += " RETURN b"

        results = self.origin.start_cypher(query, kwargs)[0]
        unwrapped = [row[0] for row in results]
        props = self.client.get_properties(*unwrapped)
        return _wrap(unwrapped, props, self.node_class)

    def _search_multi_class(self, **kwargs):
        cat_types = "|".join([c.__name__.upper() for c in self.node_classes])
        query = "MATCH (a)"
        query += _related(self.direction).format(self.relation_type)
        query += "(b)<-[r:{0}]-() ".format(cat_types)
        query += "WHERE " + _properties('b', **kwargs)
        query += " RETURN b, r"
        results = self.origin.start_cypher(query, kwargs)[0]
        return self._wrap_multi_class_resultset(results)

    def is_connected(self, obj):
        return self.origin.__node__.has_relationship_with(obj.__node__, self.direction, self.relation_type)

    def connect(self, obj):
        if self.direction == EITHER:
            raise Exception("Cannot connect with direction EITHER")
        # check if obj class is of node_class type or its subclass
        if hasattr(self, 'node_class'):
            if not self.node_class.__subclasscheck__(obj.__class__):
                raise Exception("Expected object of class (or a subclass of) " + self.node_class.__name__)
        elif hasattr(self, 'node_classes'):
            for cls in self.node_classes:
                if cls.__subclasscheck__(obj.__class__):
                    node_class = cls
            if not node_class:
                allowed_cls = ", ".join([c.__name__ for c in self.node_classes])
                raise Exception("Expected object of class of " + allowed_cls)

        if not obj.__node__:
            raise Exception("Can't create relationship to unsaved node")
        # TODO handle 'EITHER' connect correctly
        if self.direction == OUTGOING or self.direction == EITHER:
            self.client.get_or_create_relationships((self.origin.__node__, self.relation_type, obj.__node__))
        elif self.direction == INCOMING:
            self.client.get_or_create_relationships((obj.__node__, self.relation_type, self.origin.__node__))
        else:
            raise Exception("Unknown relationship direction {0}".format(self.direction))

    def reconnect(self, old_obj, new_obj):
        if self.is_connected(old_obj):
            rels = self.origin.__node__.get_relationships_with(
                    old_obj.__node__, self.direction, self.relation_type)
            for r in rels:
                r.delete()
        else:
            raise NotConnected(old_obj.__node__.id)

        self.client.get_or_create_relationships((self.origin.__node__, self.relation_type, new_obj.__node__),)

    def disconnect(self, obj):
        rels = self.origin.__node__.get_relationships_with(obj.__node__, self.direction, self.relation_type)
        if not rels:
            raise NotConnected(obj.__node__.id)
        if len(rels) > 1:
            raise Exception("Expected single relationship got {0}".format(rels))
        rels[0].delete()

    def single(self):
        nodes = self.all()
        if nodes:
            return nodes[0]
        else:
            return None


class RelationshipDefinition(object):
    def __init__(self, relation_type, cls_name, direction, manager=RelationshipManager):
        self.module_name = sys._getframe(4).f_globals['__name__']
        self.relation_type = relation_type
        self.node_class = cls_name
        self.manager = manager
        self.direction = direction

    def lookup_classes(self):
        if isinstance(self.node_class, list):
            return [self._lookup(name) for name in self.node_class]
        else:
            return self._lookup(self.node_class)

    def _lookup(self, name):
        if name.find('.') is -1:
            module = self.module_name
        else:
            module, _, name = name.rpartition('.')

        if not module in sys.modules:
            __import__(module)
        return getattr(sys.modules[module], name)

    def build_manager(self, origin, name):
        rel = self.manager(
                self.direction,
                self.relation_type,
                self.lookup_classes(),
                origin
               )
        rel.name = name
        return rel


def _relate(cls_name, direction, rel_type, cardinality=None):
    if not isinstance(cls_name, (str, unicode, list)):
        raise Exception('Expected class name or list of class names, got ' + repr(cls_name))
    if not cardinality: # TODO do we need this? - avoid circular ref
        from .cardinality import ZeroOrMore
        cardinality = ZeroOrMore
    return RelationshipDefinition(rel_type, cls_name, direction, cardinality)


def RelationshipTo(cls_name, rel_type, cardinality=None):
    return _relate(cls_name, OUTGOING, rel_type, cardinality)


def RelationshipFrom(cls_name, rel_type, cardinality=None):
    return _relate(cls_name, INCOMING, rel_type, cardinality)


def Relationship(cls_name, rel_type, cardinality=None):
    return _relate(cls_name, EITHER, rel_type, cardinality)


class NotConnected(Exception):
    pass
