from py2neo import neo4j
import sys
from .exception import DoesNotExist, NotConnected
from .util import camel_to_upper

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
        for field, value in kwargs.items():
            t.where(field, '=', value)
        return t.run()

    def is_connected(self, obj):
        rel = rel_helper(lhs='a', rhs='b', ident='r', **self.definition)
        q = "START a=node({self}), b=node({them}) MATCH" + rel + "RETURN count(r)"
        return bool(self.origin.cypher(q, {'them': obj.__node__.id})[0][0][0])

    def connect(self, obj, properties=None):
        if not hasattr(obj, '__node__'):
            raise Exception("Can't create relationship to unsaved node")

        # check for valid node class
        node_class = None
        for rel_type, cls in self.target_map.items():
            if obj.__class__ is cls:
                node_class = cls
        if not node_class:
            allowed_cls = ", ".join([tcls.__name__ for tcls, _ in self.target_map.items()])
            raise Exception("connect expected objects of class "
                    + allowed_cls + " got " + obj.__class__.__name__)

        new_rel = rel_helper(lhs='us', rhs='them', ident='r', **self.definition)
        q = "START us=node({self}), them=node({them}) CREATE UNIQUE " + new_rel

        params = {'them': obj.__node__.id}
        # copy over properties if we have
        if properties:
            for p, v in properties.items():
                params['place_holder_' + p] = v
                q += " SET r." + p + " = {place_holder_" + p + "}"

        self.origin.cypher(q, params)

    def reconnect(self, old_obj, new_obj):
        old_rel = rel_helper(lhs='us', rhs='old', ident='r', **self.definition)

        # get list of properties on the existing rel
        result, _ = self.origin.cypher("START us=node({self}), old=node({old}) MATCH " + old_rel + " RETURN r",
            {'old': old_obj.__node__.id})
        if result:
            existing_properties = result[0][0].__metadata__['data'].keys()
        else:
            raise NotConnected('reconnect', self.origin, old_obj)

        # remove old relationship and create new one
        new_rel = rel_helper(lhs='us', rhs='new', ident='r2', **self.definition)
        q = "START us=node({self}), old=node({old}), new=node({new}) MATCH " + old_rel
        q += " CREATE UNIQUE " + new_rel

        # copy over properties if we have
        for p in existing_properties:
            q += " SET r2.{} = r.{}".format(p, p)
        q += " WITH r DELETE r"

        self.origin.cypher(q, {'old': old_obj.__node__.id, 'new': new_obj.__node__.id})

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
