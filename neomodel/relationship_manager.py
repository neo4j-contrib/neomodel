import sys
import functools
from importlib import import_module
from .exception import NotConnected, MultipleNodesReturned
from .util import deprecated
from .match import OUTGOING, INCOMING, EITHER, rel_helper, Traversal, NodeSet


# check source node is saved and not deleted
def check_source(fn):
    fn_name = fn.func_name if hasattr(fn, 'func_name') else fn.__name__

    @functools.wraps(fn)
    def checker(self, *args, **kwargs):
        self.source._pre_action_check(self.name + '.' + fn_name)
        return fn(self, *args, **kwargs)
    return checker


class RelationshipManager(object):
    def __init__(self, source, key, definition):
        self.source = source
        self.source_class = source.__class__
        self.name = key
        self.definition = definition

    def __str__(self):
        direction = 'either'
        if self.definition['direction'] == OUTGOING:
            direction = 'a outgoing'
        elif self.definition['direction'] == INCOMING:
            direction = 'a incoming'

        return "{0} in {1} direction of type {2} on node ({3}) of class '{4}'".format(
            self.description, direction,
            self.definition['relation_type'], self.source.id, self.source_class.__name__)

    def _check_node(self, obj):
        """check for valid node i.e correct class and is saved"""
        if not isinstance(obj, self.definition['node_class']):
            raise ValueError("Expected node of class " + self.definition['node_class'].__name__)
        if not hasattr(obj, 'id'):
            raise ValueError("Can't perform operation on unsaved node " + repr(obj))

    @check_source
    def connect(self, obj, properties=None):
        self._check_node(obj)

        if not self.definition['model'] and properties:
            raise NotImplementedError("Relationship properties without " +
                    "using a relationship model is no longer supported")

        new_rel = rel_helper(lhs='us', rhs='them', ident='r', **self.definition)
        q = "MATCH (them), (us) WHERE id(them)={them} and id(us)={self} " \
            "CREATE UNIQUE" + new_rel
        params = {'them': obj.id}

        if not properties and not self.definition['model']:
            self.source.cypher(q, params)
            return True

        rel_model = self.definition['model']
        # need to generate defaults etc to create fake instance
        tmp = rel_model(**properties) if properties else rel_model()

        for p, v in rel_model.deflate(tmp.__properties__).items():
            params['place_holder_' + p] = v
            q += " SET r." + p + " = {place_holder_" + p + "}"

        rel_ = self.source.cypher(q + " RETURN r", params)[0][0][0]
        rel_instance = self._set_start_end_cls(rel_model.inflate(rel_), obj)
        return rel_instance

    @check_source
    def relationship(self, obj):
        """relationship: node"""
        self._check_node(obj)
        if 'model' not in self.definition:
            raise NotImplemented("'relationship' method only available on relationships"
                    + " that have a model defined")

        rel_model = self.definition['model']

        my_rel = rel_helper(lhs='us', rhs='them', ident='r', **self.definition)
        q = "MATCH (them), (us) WHERE id(them)={them} and id(us)={self} MATCH " \
            "" + my_rel + " RETURN r"
        rel = self.source.cypher(q, {'them': obj.id})[0][0][0]
        if not rel:
            return
        return self._set_start_end_cls(rel_model.inflate(rel), obj)

    def _set_start_end_cls(self, rel_instance, obj):
        if self.definition['direction'] == INCOMING:
            rel_instance._start_node_class = obj.__class__
            rel_instance._end_node_class = self.source_class
        else:
            rel_instance._start_node_class = self.source_class
            rel_instance._end_node_class = obj.__class__
        return rel_instance

    @check_source
    def reconnect(self, old_obj, new_obj):
        """reconnect: old_node, new_node"""
        self._check_node(old_obj)
        self._check_node(new_obj)
        if old_obj.id == new_obj.id:
            return
        old_rel = rel_helper(lhs='us', rhs='old', ident='r', **self.definition)

        # get list of properties on the existing rel
        result, meta = self.source.cypher(
            "MATCH (us), (old) WHERE id(us)={self} and id(old)={old} "
            "MATCH " + old_rel + " RETURN r", {'old': old_obj.id})
        if result:
            existing_properties = result[0][0].properties.keys()
        else:
            raise NotConnected('reconnect', self.source, old_obj)

        # remove old relationship and create new one
        new_rel = rel_helper(lhs='us', rhs='new', ident='r2', **self.definition)
        q = "MATCH (us), (old), (new) " \
            "WHERE id(us)={self} and id(old)={old} and id(new)={new} " \
            "MATCH " + old_rel
        q += " CREATE UNIQUE" + new_rel

        # copy over properties if we have
        for p in existing_properties:
            q += " SET r2.{} = r.{}".format(p, p)
        q += " WITH r DELETE r"

        self.source.cypher(q, {'old': old_obj.id, 'new': new_obj.id})

    @check_source
    def disconnect(self, obj):
        rel = rel_helper(lhs='a', rhs='b', ident='r', **self.definition)
        q = "MATCH (a), (b) WHERE id(a)={self} and id(b)={them} " \
            "MATCH " + rel + " DELETE r"
        self.source.cypher(q, {'them': obj.id})

    def _new_traversal(self):
        return Traversal(self.source, self.name, self.definition)

    # The methods below simply proxy the match engine.
    @check_source
    def get(self, **kwargs):
        return NodeSet(self._new_traversal()).get(**kwargs)

    @deprecated("search() is now deprecated please use filter() and exclude()")
    def search(self, **kwargs):
        return self.filter(**kwargs).all()

    def filter(self, **kwargs):
        return NodeSet(self._new_traversal()).filter(**kwargs)

    def exclude(self, **kwargs):
        return NodeSet(self._new_traversal()).exclude(**kwargs)

    @check_source
    def is_connected(self, obj):
        return self._new_traversal().__contains__(obj)

    def single(self):
        try:
            return self[0]
        except IndexError:
            pass

    def match(self, **kwargs):
        return self._new_traversal().match(**kwargs)

    def all(self):
        return self._new_traversal().all()

    def __iter__(self):
        return self._new_traversal().__iter__()

    def __len__(self):
        return self._new_traversal().__len__()

    def __bool__(self):
        return self._new_traversal().__bool__()

    def __nonzero__(self):
        return self._new_traversal().__nonzero__()

    def __contains__(self, obj):
        return self._new_traversal().__contains__(obj)

    def __getitem__(self, key):
        return self._new_traversal().__getitem__(key)


class RelationshipDefinition(object):
    def __init__(self, relation_type, cls_name, direction, manager=RelationshipManager, model=None):
        self.module_name = sys._getframe(4).f_globals['__name__']
        if '__file__' in sys._getframe(4).f_globals:
            self.module_file = sys._getframe(4).f_globals['__file__']
        self._raw_class = cls_name
        self.manager = manager
        self.definition = {}
        self.definition['relation_type'] = relation_type
        self.definition['direction'] = direction
        self.definition['model'] = model

    def _lookup_node_class(self):
        if not isinstance(self._raw_class, str):
            self.definition['node_class'] = self._raw_class
        else:
            name = self._raw_class
            if name.find('.') == -1:
                module = self.module_name
            else:
                module, _, name = name.rpartition('.')

            if module not in sys.modules:
                # yet another hack to get around python semantics
                # __name__ is the namespace of the parent module for __init__.py files,
                # and the namespace of the current module for other .py files,
                # therefore there's a need to define the namespace differently for
                # these two cases in order for . in relative imports to work correctly
                # (i.e. to mean the same thing for both cases).
                # For example in the comments below, namespace == myapp, always
                if not hasattr(self, 'module_file'):
                    raise ImportError("Couldn't lookup '{}'".format(name))

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
            self.definition['node_class'] = getattr(sys.modules[module], name)

    def build_manager(self, source, name):
        self._lookup_node_class()
        return self.manager(source, name, self.definition)


class ZeroOrMore(RelationshipManager):
    description = "zero or more relationships"


def _relate(cls_name, direction, rel_type, cardinality=None, model=None):
    if not isinstance(cls_name, (str, object)):
        raise ValueError('Expected class name or class got ' + repr(cls_name))
    from .relationship import StructuredRel # TODO

    if model and not issubclass(model, (StructuredRel,)):
        raise ValueError('model must be a StructuredRel')
    return RelationshipDefinition(rel_type, cls_name, direction, cardinality, model)


def RelationshipTo(cls_name, rel_type, cardinality=ZeroOrMore, model=None):
    return _relate(cls_name, OUTGOING, rel_type, cardinality, model)


def RelationshipFrom(cls_name, rel_type, cardinality=ZeroOrMore, model=None):
    return _relate(cls_name, INCOMING, rel_type, cardinality, model)


def Relationship(cls_name, rel_type, cardinality=ZeroOrMore, model=None):
    return _relate(cls_name, EITHER, rel_type, cardinality, model)
