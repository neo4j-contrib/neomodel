from py2neo import neo4j
import sys
from .exception import DoesNotExist, NotConnected
from .util import camel_to_upper

OUTGOING = neo4j.Direction.OUTGOING
INCOMING = neo4j.Direction.INCOMING
EITHER = neo4j.Direction.EITHER


def _related(direction):
    if direction == OUTGOING:
        return '-[:{0}]->'
    elif direction == INCOMING:
        return '<-[:{0}]-'
    return '-[:{0}]-'


def _properties(ident, **kwargs):
    props = [ident + '.' + k + '! = {' + k + '}' for k in kwargs]
    return '(' + ', '.join(props) + ')'


class RelationshipManager(object):
    def __init__(self, direction, relation_type, node_classes, origin):
        self.direction = direction
        self.relation_type = relation_type
        self.node_classes = node_classes if isinstance(node_classes, list) else [node_classes]
        self.class_map = dict(zip([camel_to_upper(c.__name__)
            for c in self.node_classes], self.node_classes))
        self.origin = origin

    def __str__(self):
        direction = 'either'
        if self.direction == OUTGOING:
            direction = 'a outgoing'
        elif self.direction == INCOMING:
            direction = 'a incoming'

        return "{0} in {1} direction of type {2} on node ({3}) of class '{4}'".format(
            self.description, direction,
            self.relation_type, self.origin.__node__.id, self.origin.__class__.__name__)

    def __bool__(self):
        return self.__len__() > 0

    def __nonezero__(self):
        return self.__len__() > 0

    def __len__(self):
        query = "START a=node({self}) MATCH (a)"
        query += _related(self.direction).format(self.relation_type)
        query += "(x) RETURN COUNT(x)"
        return int(self.origin.cypher(query)[0][0][0])

    @property
    def client(self):
        return self.origin.client

    def count(self):
        return self.__len__()

    def _all_query(self):
        cat_types = "|".join([camel_to_upper(c.__name__) for c in self.node_classes])
        query = "START a=node({self}) MATCH (a)"
        query += _related(self.direction).format(self.relation_type)
        query += "(x)<-[r:{0}]-() WHERE r.__instance__! = true RETURN x, r".format(cat_types)
        return query

    def all(self):
        results = self.origin.cypher(self._all_query())[0]
        return self._inflate_nodes_by_rel(results)

    def _inflate_nodes_by_rel(self, results):
        "wrap each node in correct class based on rel.type"
        nodes = [row[0] for row in results]
        classes = [self.class_map[row[1].type] for row in results]
        return [cls.inflate(node) for node, cls in zip(nodes, classes)]

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
            return self.all()
        cat_types = "|".join([camel_to_upper(c.__name__) for c in self.node_classes])
        query = "START a=node({self}) MATCH (a)"
        query += _related(self.direction).format(self.relation_type)
        query += "(b)<-[r:{0}]-() ".format(cat_types)
        query += "WHERE r.__instance__! = true AND " + _properties('b', **kwargs)
        query += " RETURN b, r"
        results = self.origin.cypher(query, kwargs)[0]
        return self._inflate_nodes_by_rel(results)

    def is_connected(self, obj):
        return self.origin.__node__.has_relationship_with(obj.__node__, self.direction, self.relation_type)

    def connect(self, obj, properties=None):
        if not obj.__node__:
            raise Exception("Can't create relationship to unsaved node")
        if self.direction == EITHER:
            raise Exception("Cannot connect with direction EITHER")

        node_class = None
        for cls in self.node_classes:
            if obj.__class__ is cls:
                node_class = cls
        if not node_class:
            allowed_cls = ", ".join([c.__name__ for c in self.node_classes])
            raise Exception("Expected object of class of "
                    + allowed_cls + " got " + obj.__class__.__name__)

        if self.direction == OUTGOING:
            self.client.get_or_create_relationships((self.origin.__node__, self.relation_type,
                obj.__node__, properties))
        elif self.direction == INCOMING:
            self.client.get_or_create_relationships((obj.__node__, self.relation_type,
                self.origin.__node__, properties))
        else:
            raise Exception("Unknown relationship direction {0}".format(self.direction))

    def reconnect(self, old_obj, new_obj):
        properties = {}
        if self.is_connected(old_obj):
            rels = self.origin.__node__.get_relationships_with(
                old_obj.__node__, self.direction, self.relation_type)
            for r in rels:
                properties.update(r.get_properties())
                r.delete()
        else:
            raise NotConnected('reconnect', self.origin, old_obj)

        self.client.get_or_create_relationships((self.origin.__node__, self.relation_type, new_obj.__node__, properties),)

    def disconnect(self, obj):
        rels = self.origin.__node__.get_relationships_with(obj.__node__, self.direction, self.relation_type)
        if not rels:
            raise NotConnected('disconnect', self.origin, obj)
        if len(rels) > 1:
            raise Exception("Expected single relationship got {0}".format(rels))
        rels[0].delete()

    def single(self):
        results = self.origin.cypher(self._all_query() + " LIMIT 1")[0]
        nodes = self._inflate_nodes_by_rel(results)
        return nodes[0] if nodes else None


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
            return [self._lookup(self.node_class)]

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
            origin)
        rel.name = name
        return rel


class ZeroOrMore(RelationshipManager):
    description = "zero or more relationships"


def _relate(cls_name, direction, rel_type, cardinality=None):
    if not isinstance(cls_name, (str, unicode, list)):
        raise Exception('Expected class name or list of class names, got ' + repr(cls_name))
    return RelationshipDefinition(rel_type, cls_name, direction, cardinality)


def RelationshipTo(cls_name, rel_type, cardinality=ZeroOrMore):
    return _relate(cls_name, OUTGOING, rel_type, cardinality)


def RelationshipFrom(cls_name, rel_type, cardinality=ZeroOrMore):
    return _relate(cls_name, INCOMING, rel_type, cardinality)


def Relationship(cls_name, rel_type, cardinality=ZeroOrMore):
    return _relate(cls_name, EITHER, rel_type, cardinality)
