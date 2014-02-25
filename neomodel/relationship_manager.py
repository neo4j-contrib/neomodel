import sys
import functools
from importlib import import_module
from .exception import DoesNotExist, NotConnected


OUTGOING, INCOMING, EITHER = 1, -1, 0


# check origin node is saved and not deleted
def check_origin(fn):
    fn_name = fn.func_name if hasattr(fn, 'func_name') else fn.__name__

    @functools.wraps(fn)
    def checker(self, *args, **kwargs):
        self.origin._pre_action_check(self.name + '.' + fn_name)
        return fn(self, *args, **kwargs)
    return checker


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
        self.label_map = definition['label_map']
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
            self.relation_type, self.origin._id, self.origin.__class__.__name__)

    @check_origin
    def __bool__(self):
        return len(self) > 0

    @check_origin
    def __nonzero__(self):
        return len(self) > 0

    @check_origin
    def __len__(self):
        return len(self.origin.traverse(self.name))

    @property
    def client(self):
        return self.origin.client

    @check_origin
    def count(self):
        return self.__len__()

    @check_origin
    def all(self):
        return self.origin.traverse(self.name).run()

    @check_origin
    def get(self, **kwargs):
        result = self.search(**kwargs)
        if len(result) == 1:
            return result[0]
        if len(result) > 1:
            raise Exception("Multiple items returned, use search?")
        if not result:
            raise DoesNotExist("No items exist for the specified arguments")

    @check_origin
    def search(self, **kwargs):
        t = self.origin.traverse(self.name)
        for field, value in kwargs.items():
            t.where(field, '=', value)
        return t.run()

    @check_origin
    def is_connected(self, obj):
        self._check_node(obj)

        rel = rel_helper(lhs='a', rhs='b', ident='r', **self.definition)
        q = "START a=node({self}), b=node({them}) MATCH" + rel + "RETURN count(r)"
        return bool(self.origin.cypher(q, {'them': obj._id})[0][0][0])

    def _check_node(self, obj):
        """check for valid node i.e correct class and is saved"""
        for label, cls in self.label_map.items():
            if issubclass(obj.__class__, cls) and label in obj.labels():
                if not hasattr(obj, '_id'):
                    raise ValueError("Can't preform operation on unsaved node " + repr(obj))
                return

        allowed_cls = ", ".join([(tcls if isinstance(tcls, str) else tcls.__name__)
                                 for tcls, _ in self.label_map.items()])
        raise ValueError("Expected nodes of class "
                + allowed_cls + " got " + repr(obj)
                + " see relationship definition in " + self.origin.__class__.__name__)

    @check_origin
    def connect(self, obj, properties=None):
        self._check_node(obj)

        new_rel = rel_helper(lhs='us', rhs='them', ident='r', **self.definition)
        q = "START them=node({them}), us=node({self}) CREATE UNIQUE" + new_rel
        params = {'them': obj._id}

        if not properties and not self.definition['model']:
            self.origin.cypher(q, params)
            return True


        if self.definition['model']:
            rel_model = self.definition['model']
            # need to generate defaults etc to create fake instance
            tmp = rel_model(**properties) if properties else rel_model()

            for p, v in rel_model.deflate(tmp.__properties__).items():
                params['place_holder_' + p] = v
                q += " SET r." + p + " = {place_holder_" + p + "}"

            rel_ = self.origin.cypher(q + " RETURN r", params)[0][0][0]
            rel_instance = rel_model.inflate(rel_)

            if self.definition['direction'] == INCOMING:
                rel_instance._start_node_class = obj.__class__
                rel_instance._end_node_class = self.origin.__class__
            else:
                rel_instance._start_node_class = self.origin.__class__
                rel_instance._end_node_class = obj.__class__

            self.origin.cypher(q, params)
            return rel_instance

        if properties:
            for p, v in properties.items():
                params['place_holder_' + p] = v
                q += " SET r." + p + " = {place_holder_" + p + "}"

        self.origin.cypher(q, params)

    @check_origin
    def relationship(self, obj):
        """relationship: node"""
        self._check_node(obj)
        if not 'model' in self.definition:
            raise NotImplemented("'relationship' method only available on relationships"
                    + " that have a model defined")

        rel_model = self.definition['model']

        new_rel = rel_helper(lhs='us', rhs='them', ident='r', **self.definition)
        q = "START them=node({them}), us=node({self}) MATCH " + new_rel + " RETURN r"
        rel = self.origin.cypher(q, {'them': obj._id})[0][0][0]
        if not rel:
            return
        rel_instance = rel_model.inflate(rel)

        if self.definition['direction'] == INCOMING:
            rel_instance._start_node_class = obj.__class__
            rel_instance._end_node_class = self.origin.__class__
        else:
            rel_instance._start_node_class = self.origin.__class__
            rel_instance._end_node_class = obj.__class__
        return rel_instance

    @check_origin
    def reconnect(self, old_obj, new_obj):
        """reconnect: old_node, new_node"""
        self._check_node(old_obj)
        self._check_node(new_obj)
        if old_obj._id == new_obj._id:
            return
        old_rel = rel_helper(lhs='us', rhs='old', ident='r', **self.definition)

        # get list of properties on the existing rel
        result, meta = self.origin.cypher("START us=node({self}), old=node({old}) MATCH " + old_rel + " RETURN r",
            {'old': old_obj._id})
        if result:
            existing_properties = result[0][0]._properties.keys()
        else:
            raise NotConnected('reconnect', self.origin, old_obj)

        # remove old relationship and create new one
        new_rel = rel_helper(lhs='us', rhs='new', ident='r2', **self.definition)
        q = "START us=node({self}), old=node({old}), new=node({new}) MATCH " + old_rel
        q += " CREATE UNIQUE" + new_rel

        # copy over properties if we have
        for p in existing_properties:
            q += " SET r2.{} = r.{}".format(p, p)
        q += " WITH r DELETE r"

        self.origin.cypher(q, {'old': old_obj._id, 'new': new_obj._id})

    @check_origin
    def disconnect(self, obj):
        rel = rel_helper(lhs='a', rhs='b', ident='r', **self.definition)
        q = "START a=node({self}), b=node({them}) MATCH " + rel + " DELETE r"
        self.origin.cypher(q, {'them': obj._id})

    @check_origin
    def single(self):
        nodes = self.origin.traverse(self.name).limit(1).run()
        return nodes[0] if nodes else None


class RelationshipDefinition(object):
    def __init__(self, relation_type, cls_name, direction, manager=RelationshipManager, model=None):
        self.module_name = sys._getframe(4).f_globals['__name__']
        self.module_file = sys._getframe(4).f_globals['__file__']
        self.node_class = cls_name
        self.manager = manager
        self.definition = {}
        self.definition['relation_type'] = relation_type
        self.definition['direction'] = direction
        self.definition['model'] = model

    def _lookup(self, name):
        if name.find('.') == -1:
            module = self.module_name
        else:
            module, _, name = name.rpartition('.')

        if not module in sys.modules:
            # yet another hack to get around python semantics
            # __name__ is the namespace of the parent module for __init__.py files,
            # and the namespace of the current module for other .py files,
            # therefore there's a need to define the namespace differently for
            # these two cases in order for . in relative imports to work correctly
            # (i.e. to mean the same thing for both cases).
            # For example in the comments below, namespace == myapp, always
            if '__init__.py' in self.module_file:
                # e.g. myapp/__init__.py -[__name__]-> myapp
                namespace = self.module_name
            else:
                # e.g. myapp/models.py -[__name__]-> myapp.models
                namespace = self.module_name.rpartition('.')[0]

            # load a module from a namespace (e.g. models from myapp)
            if module:
                module = import_module(module, namespace).__name__
            # load the namespace itself (e.g. myapp)
            # (otherwise it would look like import . from myapp)
            else:
                module = import_module(namespace).__name__
        return getattr(sys.modules[module], name)

    def build_manager(self, origin, name):
        # get classes for related nodes
        if isinstance(self.node_class, list):
            node_classes = [self._lookup(cls) if isinstance(cls, (str,)) else cls
                        for cls in self.node_class]
        else:
            node_classes = [self._lookup(self.node_class)
                if isinstance(self.node_class, (str,)) else self.node_class]

        # build label map
        self.definition['label_map'] = dict(zip([c.__label__
                for c in node_classes], node_classes))
        rel = self.manager(self.definition, origin)
        rel.name = name
        return rel


class ZeroOrMore(RelationshipManager):
    description = "zero or more relationships"


def _relate(cls_name, direction, rel_type, cardinality=None, model=None):
    if not isinstance(cls_name, (str, list, object)):
        raise ValueError('Expected class name or list of class names, got ' + repr(cls_name))
    from .relationship import StructuredRel
    if model and not issubclass(model, (StructuredRel,)):
        raise ValueError('model must be a StructuredRel')
    return RelationshipDefinition(rel_type, cls_name, direction, cardinality, model)


def RelationshipTo(cls_name, rel_type, cardinality=ZeroOrMore, model=None):
    return _relate(cls_name, OUTGOING, rel_type, cardinality, model)


def RelationshipFrom(cls_name, rel_type, cardinality=ZeroOrMore, model=None):
    return _relate(cls_name, INCOMING, rel_type, cardinality, model)


def Relationship(cls_name, rel_type, cardinality=ZeroOrMore, model=None):
    return _relate(cls_name, EITHER, rel_type, cardinality, model)
