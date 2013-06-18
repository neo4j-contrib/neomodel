from py2neo import neo4j
import sys
from .exception import DoesNotExist, NotConnected
from .util import camel_to_upper, items

OUTGOING = neo4j.Direction.OUTGOING
INCOMING = neo4j.Direction.INCOMING
EITHER = neo4j.Direction.EITHER


def rel_helper(**rel):
    if rel['direction'] == OUTGOING:
        stmt = '-[{0}:{1}]->'
    elif rel['direction'] == INCOMING:
        stmt = '<-[{0}:{1}]-'
    else:
        stmt = '-[{0}:{1}]-'
    ident = rel['ident'] if 'ident' in rel else ''
    stmt = stmt.format(ident, rel['relation_type'])
    return "  ({0}){1}({2})".format(rel['lhs'], stmt, rel['rhs'])


class RelationshipManager(object):
    def __init__(self, definition, origin):
        self.direction = definition['direction']
        self.relation_type = definition['relation_type']
        self.target_map = definition['target_map']
        self.definition = definition
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
        return len(self) > 0

    def __nonzero__(self):
        return len(self) > 0

    def __len__(self):
        return len(self.origin.traverse(self.name))

    @property
    def client(self):
        return self.origin.client

    def count(self):
        return self.__len__()

    def all(self):
        return self.origin.traverse(self.name).run()

    def get(self, **kwargs):
        result = self.search(**kwargs)
        if len(result) == 1:
            return result[0]
        if len(result) > 1:
            raise Exception("Multiple items returned, use search?")
        if not result:
            raise DoesNotExist("No items exist for the specified arguments")

    def search(self, **kwargs):
        t = self.origin.traverse(self.name)
        for field, value in items(kwargs):
            t.where(field, '=', value)
        return t.run()

    def is_connected(self, obj):
        rel = rel_helper(lhs='a', rhs='b', ident='r', **self.definition)
        q = "START a=node({self}), b=node({them}) MATCH" + rel + "RETURN count(r)"
        return bool(self.origin.cypher(q, {'them': obj.__node__.id})[0][0][0])

    def connect(self, obj, properties=None):
        if not hasattr(obj, '__node__'):
            raise Exception("Can't create relationship to unsaved node")
        direction = OUTGOING if self.direction == EITHER else self.direction

        node_class = None
        for rel_type, cls in items(self.target_map):
            if obj.__class__ is cls:
                node_class = cls
        if not node_class:
            allowed_cls = ", ".join([tcls.__name__ for tcls, _ in items(self.target_map)])
            raise Exception("connect expected objects of class "
                    + allowed_cls + " got " + obj.__class__.__name__)

        if not properties:
            properties = {}

        if direction == OUTGOING:
                self.origin.__node__.get_or_create_path(
                        (self.relation_type, properties), obj.__node__)
        elif direction == INCOMING:
            obj.__node__.get_or_create_path(
                    (self.relation_type, properties), self.origin.__node__)

    def reconnect(self, old_obj, new_obj):
        if not self.is_connected(old_obj):
            raise NotConnected('reconnect', self.origin, old_obj)

        properties = {}

        rel = rel_helper(lhs='a', rhs='b', ident='r', **self.definition)
        q = "START a=node({self}), b=node({them}) MATCH " + rel + " RETURN r"
        for r in self.origin.cypher(q, {'them': old_obj.__node__.id})[0][0]:
            properties.update(r.get_properties())
        self.disconnect(old_obj)

        self.connect(new_obj, properties)

    def disconnect(self, obj):
        rel = rel_helper(lhs='a', rhs='b', ident='r', **self.definition)
        q = "START a=node({self}), b=node({them}) MATCH " + rel + " DELETE r"
        self.origin.cypher(q, {'them': obj.__node__.id}),

    def single(self):
        nodes = self.origin.traverse(self.name).limit(1).run()
        return nodes[0] if nodes else None


class RelationshipDefinition(object):
    def __init__(self, relation_type, cls_name, direction, manager=RelationshipManager):
        self.module_name = sys._getframe(4).f_globals['__name__']
        self.node_class = cls_name
        self.manager = manager
        self.definition = {}
        self.definition['relation_type'] = relation_type
        self.definition['direction'] = direction

    def _lookup(self, name):
        if name.find('.') is -1:
            module = self.module_name
        else:
            module, _, name = name.rpartition('.')

        if not module in sys.modules:
            __import__(module)
        return getattr(sys.modules[module], name)

    def build_manager(self, origin, name):
        # get classes for target
        if isinstance(self.node_class, list):
            node_classes = [self._lookup(cls) if isinstance(cls, (str,)) else cls
                        for cls in self.node_class]
        else:
            node_classes = [self._lookup(self.node_class)
                if isinstance(self.node_class, (str,)) else self.node_class]

        # build target map
        self.definition['target_map'] = dict(zip([camel_to_upper(c.__name__)
                for c in node_classes], node_classes))
        rel = self.manager(self.definition, origin)
        rel.name = name
        return rel


class ZeroOrMore(RelationshipManager):
    description = "zero or more relationships"


def _relate(cls_name, direction, rel_type, cardinality=None):
    if not isinstance(cls_name, (str, list, object)):
        raise Exception('Expected class name or list of class names, got ' + repr(cls_name))
    return RelationshipDefinition(rel_type, cls_name, direction, cardinality)


def RelationshipTo(cls_name, rel_type, cardinality=ZeroOrMore):
    return _relate(cls_name, OUTGOING, rel_type, cardinality)


def RelationshipFrom(cls_name, rel_type, cardinality=ZeroOrMore):
    return _relate(cls_name, INCOMING, rel_type, cardinality)


def Relationship(cls_name, rel_type, cardinality=ZeroOrMore):
    return _relate(cls_name, EITHER, rel_type, cardinality)
