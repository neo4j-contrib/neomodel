from py2neo import neo4j
import sys
from .exception import DoesNotExist
from .util import camel_to_upper

OUTGOING = neo4j.Direction.OUTGOING
INCOMING = neo4j.Direction.INCOMING
EITHER = neo4j.Direction.EITHER


def _dir_2_str(direction):
    if direction == OUTGOING:
        return 'a outgoing'
    elif direction == INCOMING:
        return 'a incoming'
    else:
        return 'either'


def _related(direction):
    if direction == OUTGOING:
        return '-[:{0}]->'
    elif direction == INCOMING:
        return '<-[:{0}]-'
    else:
        return '-[:{0}]-'


def _properties(ident, **kwargs):
    props = [ident + '.' + k + '! = {' + k + '}' for k in kwargs]
    return '(' + ', '.join(props) + ')'


class RelationshipManager(object):
    def __init__(self, direction, relation_type, node_classes, origin):
        self.direction = direction
        self.relation_type = relation_type
        if isinstance(node_classes, list):
            self.node_classes = node_classes
            self.class_map = dict(zip([camel_to_upper(c.__name__) for c in node_classes],
                node_classes))
        else:
            self.node_class = node_classes
        self.origin = origin

    def __str__(self):
        return "{0} in {1} direction of type {2} on node ({3}) of class '{4}'".format(
                self._cardinality_as_str(), _dir_2_str(self.direction),
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

    def all(self):
        if hasattr(self, 'node_classes'):
            return self._all_multi_class()
        else:
            return self._all_single_class()

    def _inflate_nodes_by_rel(self, results):
        """With resultset containing [node, rel] pairs
        wrap each node in correct neomodel class based on rel.type"""
        nodes = [row[0] for row in results]
        classes = [self.class_map[row[1].type] for row in results]
        return [cls.inflate(node) for node, cls in zip(nodes, classes)]

    def _all_multi_class(self):
        cat_types = "|".join([camel_to_upper(c.__name__) for c in self.node_classes])
        query = "START a=node({self}) MATCH (a)"
        query += _related(self.direction).format(self.relation_type)
        query += "(x)<-[r:{0}]-() WHERE r.__instance__! = true RETURN x, r".format(cat_types)
        results = self.origin.cypher(query)[0]
        return self._inflate_nodes_by_rel(results)

    def _all_single_class(self):
        query = "START a=node({self}) MATCH (a)"
        query += _related(self.direction).format(self.relation_type) + "(x) RETURN x"
        results = self.origin.cypher(query)
        return [self.node_class.inflate(n[0]) for n in results[0]] if results else []

    def get(self, **kwargs):
        result = self.search(**kwargs)
        if len(result) == 1:
            return result[0]
        if len(result) > 1:
            raise Exception("Multiple items returned")
        if not result:
            if hasattr(self, 'node_class'):
                raise self.node_class.DoesNotExist("No items exist for the specified arguments")
            else:
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
        query = "START a=node({self}) MATCH (a)"
        query += _related(self.direction).format(self.relation_type)
        query += "(b) WHERE " + _properties('b', **kwargs)
        query += " RETURN b"

        results = self.origin.cypher(query, kwargs)[0]
        return [self.node_class.inflate(row[0]) for row in results]

    def _search_multi_class(self, **kwargs):
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

    def connect(self, obj):
        if self.direction == EITHER:
            raise Exception("Cannot connect with direction EITHER")
        # is single class rel
        if hasattr(self, 'node_class'):
            if not self.node_class.__subclasscheck__(obj.__class__):
                raise Exception("Expected object of class (or a subclass of) {0} got {1}".format(self.node_class, obj.__class__))
        # or is multi class rel
        elif hasattr(self, 'node_classes'):
            for cls in self.node_classes:
                if cls.__subclasscheck__(obj.__class__):
                    node_class = cls
            if not node_class:
                allowed_cls = ", ".join([c.__name__ for c in self.node_classes])
                raise Exception("Expected object of class of "
                        + allowed_cls + " got " + obj.__class__.__name__)

        if not obj.__node__:
            raise Exception("Can't create relationship to unsaved node")
        if self.direction == OUTGOING:
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
