from py2neo import neo4j
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
        for node, properties in dict(zip(unwrapped, props)).iteritems():
            wrapped_node = cls(**(properties))
            wrapped_node._node = node
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
            wrapped_node._node = node
            nodes.append(wrapped_node)
        return nodes

    def _all_multi_class(self):
        cat_types = "|".join([c.__name__.upper() for c in self.node_classes])
        query = "MATCH (a)" + _related(self.direction).format(self.relation_type)
        query += "(x)<-[r:{0}]-() RETURN x, r".format(cat_types)
        results = self.origin.start_cypher(query)[0]
        return self._wrap_multi_class_resultset(results)

    def _all_single_class(self):
        related_nodes = self.origin._node.get_related_nodes(self.direction, self.relation_type)
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
            raise DoesNotExist

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
        return self.origin._node.has_relationship_with(obj._node, self.direction, self.relation_type)

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

        if not obj._node:
            raise Exception("Can't create relationship to unsaved node")
        # TODO handle 'EITHER' connect correctly
        if self.direction == OUTGOING or self.direction == EITHER:
            self.client.get_or_create_relationships((self.origin._node, self.relation_type, obj._node))
        elif self.direction == INCOMING:
            self.client.get_or_create_relationships((obj._node, self.relation_type, self.origin._node))
        else:
            raise Exception("Unknown relationship direction {0}".format(self.direction))

    def reconnect(self, old_obj, new_obj):
        if self.is_connected(old_obj):
            rels = self.origin._node.get_relationships_with(
                    old_obj._node, self.direction, self.relation_type)
            for r in rels:
                r.delete()
        else:
            raise NotConnected(old_obj._node.id)

        self.client.get_or_create_relationships((self.origin._node, self.relation_type, new_obj._node),)

    def disconnect(self, obj):
        rels = self.origin._node.get_relationships_with(obj._node, self.direction, self.relation_type)
        if not rels:
            raise NotConnected(obj._node.id)
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
    def __init__(self, relation_type, cls, direction, manager=RelationshipManager):
        self.relation_type = relation_type
        self.node_class = cls
        self.manager = manager
        self.direction = direction

    def build_manager(self, origin, name):
        rel = self.manager(
                self.direction,
                self.relation_type,
                self.node_class,
                origin
               )
        rel.name = name
        return rel


class RelationshipInstaller(object):
    """Replace relationship definitions with instances of RelationshipManager"""

    def __init__(self, *args, **kwargs):
        self._related = {}

        for key, value in self.__class__.__dict__.iteritems():
            if value.__class__ == RelationshipDefinition\
                    or issubclass(value.__class__, RelationshipDefinition):
                self._setup_relationship(key, value)

    def _setup_relationship(self, rel_name, rel_object):
        self.__dict__[rel_name] = rel_object.build_manager(self, rel_name)

    @classmethod
    def outgoing(cls, relation, alias, to=None, cardinality=None):
        cls._relate(alias, (OUTGOING, relation), to, cardinality)

    @classmethod
    def incoming(cls, relation, alias, to=None, cardinality=None):
        cls._relate(alias, (INCOMING, relation), to, cardinality)

    @classmethod
    def either(cls, relation, alias, to=None, cardinality=None):
        cls._relate(alias, (EITHER, relation), to, cardinality)

    @classmethod
    def _relate(cls, manager_property, relation, to=None, cardinality=None):
        if not cardinality:
            from .cardinality import ZeroOrMore
            cardinality = ZeroOrMore
        direction, rel_type = relation
        if hasattr(cls, manager_property):
            raise Exception(cls.__name__ + " already has attribute " + manager_property)
        relationship = RelationshipDefinition(rel_type, to, direction, cardinality)
        setattr(cls, manager_property, relationship)


class NotConnected(Exception):
    pass
