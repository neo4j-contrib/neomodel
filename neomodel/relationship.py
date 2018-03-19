import sys
from functools import wraps
from importlib import import_module

from neomodel.bases import PropertyManager, PropertyManagerMeta
from neomodel.db import client
from neomodel.exceptions import (
    AttemptedCardinalityViolation, CardinalityViolation,
    NodeIsDeletedError, NotConnected, UnsavedNodeError
)
from neomodel.hooks import hooks
from neomodel.match import (
    EITHER, INCOMING, OUTGOING, NodeSet, Traversal, _rel_helper
)
from neomodel.types import RelationshipType, RelationshipDefinitionType


# relationship models


class RelationshipMeta(PropertyManagerMeta):
    @staticmethod
    def _setup_property(cls, name, definition):
        if definition.is_indexed:
            raise NotImplementedError(
                "Indexed relationship properties not supported yet."
            )
        super()._setup_property(cls, name, definition)


class StructuredRel(PropertyManager, RelationshipType, metaclass=RelationshipMeta):
    """
    Base class for relationship objects
    """
    @hooks
    def save(self):
        """
        Save the relationship

        :return: self
        """
        props = self.deflate(self.__properties__)
        query = "MATCH ()-[r]->() WHERE id(r)={self} "
        for key in props:
            query += " SET r.{} = {{{}}}".format(key, key)
        props['self'] = self.id

        client.cypher_query(query, props)

        return self

    def start_node(self):
        """
        Get start node

        :return: StructuredNode
        """
        node = self._start_node_class()
        node.id = self._start_node_id
        node.refresh()
        return node

    def end_node(self):
        """
        Get end node

        :return: StructuredNode
        """
        node = self._end_node_class()
        node.id = self._end_node_id
        node.refresh()
        return node

    @classmethod
    def inflate(cls, rel):
        """
        Inflate a neo4j_driver relationship object to a neomodel object
        :param rel:
        :return: StructuredRel
        """
        props = {}
        for name, definition in cls.__property_definitions__.items():
            if name in rel:
                props[name] = definition.inflate(rel[name], obj=rel)
            elif definition.has_default:
                props[name] = definition.default_value()
            else:
                props[name] = None
        srel = cls(**props)
        srel._start_node_id = rel.start
        srel._end_node_id = rel.end
        srel.id = rel.id
        return srel


# relationship manager


def ensure_node_exists_in_db(method):
    """
    Decorates relationship methods that require the related node's record in
    the database.
    """
    deleted_msg = method.__qualname__ + '{}() attempted on deleted node.'
    unsaved_msg = method.__qualname__ + '{}() attempted on unsaved node.'

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if getattr(self.source, '__deleted__', False):
            raise NodeIsDeletedError(deleted_msg)
        if not hasattr(self.source, 'id'):
            raise UnsavedNodeError(unsaved_msg)
        return method(self, *args, **kwargs)
    return wrapper


class RelationshipManager:
    """
    Base class for all relationships managed through neomodel.

    I.e the 'friends' object in  `user.friends.all()`
    """
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

    @ensure_node_exists_in_db
    def connect(self, node, properties=None):
        """
        Connect a node

        :param node:
        :param properties: for the new relationship
        :type: dict
        :return:
        """
        self._check_node(node)

        if not self.definition['model'] and properties:
            raise NotImplementedError(
                "Relationship properties without using a relationship model "
                "is no longer supported."
            )

        params = {}
        rel_model = self.definition['model']
        rp = None  # rel_properties

        if rel_model:
            rp = {}
            # need to generate defaults etc to create fake instance
            tmp = rel_model(**properties) if properties else rel_model()
            # build params and place holders to pass to rel_helper
            for p, v in rel_model.deflate(tmp.__properties__).items():
                rp[p] = '{' + p + '}'
                params[p] = v

            if hasattr(tmp, 'pre_save'):
                tmp.pre_save()

        new_rel = _rel_helper(lhs='us', rhs='them', ident='r', relation_properties=rp, **self.definition)
        q = "MATCH (them), (us) WHERE id(them)={them} and id(us)={self} " \
            "CREATE UNIQUE" + new_rel

        params['them'] = node.id

        if not rel_model:
            self.source.cypher(q, params)
            return True

        rel_ = self.source.cypher(q + " RETURN r", params)[0][0][0]
        rel_instance = self._set_start_end_cls(rel_model.inflate(rel_), node)

        if hasattr(rel_instance, 'post_save'):
            rel_instance.post_save()

        return rel_instance

    @ensure_node_exists_in_db
    def relationship(self, node):
        """
        Retrieve the relationship object for this first relationship between self and node.

        :param node:
        :return: StructuredRel
        """
        self._check_node(node)
        my_rel = _rel_helper(lhs='us', rhs='them', ident='r', **self.definition)
        q = "MATCH " + my_rel + " WHERE id(them)={them} and id(us)={self} RETURN r LIMIT 1"
        rels = self.source.cypher(q, {'them': node.id})[0]
        if not rels:
            return

        rel_model = self.definition.get('model') or StructuredRel

        return self._set_start_end_cls(rel_model.inflate(rels[0][0]), node)

    @ensure_node_exists_in_db
    def all_relationships(self, node):
        """
        Retrieve all relationship objects between self and node.

        :param node:
        :return: [StructuredRel]
        """
        self._check_node(node)

        my_rel = _rel_helper(lhs='us', rhs='them', ident='r', **self.definition)
        q = "MATCH " + my_rel + " WHERE id(them)={them} and id(us)={self} RETURN r "
        rels = self.source.cypher(q, {'them': node.id})[0]
        if not rels:
            return []

        rel_model = self.definition.get('model') or StructuredRel
        return [self._set_start_end_cls(rel_model.inflate(rel[0]), node) for rel in rels]

    def _set_start_end_cls(self, rel_instance, obj):
        if self.definition['direction'] == INCOMING:
            rel_instance._start_node_class = obj.__class__
            rel_instance._end_node_class = self.source_class
        else:
            rel_instance._start_node_class = self.source_class
            rel_instance._end_node_class = obj.__class__
        return rel_instance

    @ensure_node_exists_in_db
    def reconnect(self, old_node, new_node):
        """
        Disconnect old_node and connect new_node copying over any properties on the original relationship.

        Useful for preventing cardinality violations

        :param old_node:
        :param new_node:
        :return: None
        """

        self._check_node(old_node)
        self._check_node(new_node)
        if old_node.id == new_node.id:
            return
        old_rel = _rel_helper(lhs='us', rhs='old', ident='r', **self.definition)

        # get list of properties on the existing rel
        result, meta = self.source.cypher(
            "MATCH (us), (old) WHERE id(us)={self} and id(old)={old} "
            "MATCH " + old_rel + " RETURN r", {'old': old_node.id})
        if result:
            existing_properties = result[0][0].properties.keys()
        else:
            raise NotConnected('reconnect', self.source, old_node)

        # remove old relationship and create new one
        new_rel = _rel_helper(lhs='us', rhs='new', ident='r2', **self.definition)
        q = "MATCH (us), (old), (new) " \
            "WHERE id(us)={self} and id(old)={old} and id(new)={new} " \
            "MATCH " + old_rel
        q += " CREATE UNIQUE" + new_rel

        # copy over properties if we have
        for p in existing_properties:
            q += " SET r2.{} = r.{}".format(p, p)
        q += " WITH r DELETE r"

        self.source.cypher(q, {'old': old_node.id, 'new': new_node.id})

    @ensure_node_exists_in_db
    def disconnect(self, node):
        """
        Disconnect a node

        :param node:
        :return:
        """
        rel = _rel_helper(lhs='a', rhs='b', ident='r', **self.definition)
        q = "MATCH (a), (b) WHERE id(a)={self} and id(b)={them} " \
            "MATCH " + rel + " DELETE r"
        self.source.cypher(q, {'them': node.id})

    @ensure_node_exists_in_db
    def _new_traversal(self):
        return Traversal(self.source, self.name, self.definition)

    # The methods below simply proxy the match engine.
    def get(self, **kwargs):
        """
        Retrieve a related node with the matching node properties.

        :param kwargs: same syntax as `NodeSet.filter()`
        :return: node
        """
        return NodeSet(self._new_traversal()).get(**kwargs)

    def get_or_none(self, **kwargs):
        """
        Retrieve a related node with the matching node properties or return None.

        :param kwargs: same syntax as `NodeSet.filter()`
        :return: node
        """
        return NodeSet(self._new_traversal()).get_or_none(**kwargs)

    def filter(self, **kwargs):
        """
        Retrieve related nodes matching the provided properties.

        :param kwargs: same syntax as `NodeSet.filter()`
        :return: NodeSet
        """
        return NodeSet(self._new_traversal()).filter(**kwargs)

    def order_by(self, *props):
        """
        Order related nodes by specified properties

        :param props:
        :return: NodeSet
        """
        return NodeSet(self._new_traversal()).order_by(*props)

    def exclude(self, **kwargs):
        """
        Exclude nodes that match the provided properties.

        :param kwargs: same syntax as `NodeSet.filter()`
        :return: NodeSet
        """
        return NodeSet(self._new_traversal()).exclude(**kwargs)

    def is_connected(self, node):
        """
        Check if a node is connected with this relationship type
        :param node:
        :return: bool
        """
        return self._new_traversal().__contains__(node)

    def single(self):
        """
        Get a single related node or none.

        :return: StructuredNode
        """
        try:
            return self[0]
        except IndexError:
            pass

    def match(self, **kwargs):
        """
        Return set of nodes who's relationship properties match supplied args

        :param kwargs: same syntax as `NodeSet.filter()`
        :return: NodeSet
        """
        return self._new_traversal().match(**kwargs)

    def all(self):
        """
        Return all related nodes.

        :return: list
        """
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


# cardinalities


class ZeroOrOne(RelationshipManager):
    """ A relationship to zero or one node. """
    description = "zero or one relationship"

    def single(self):
        """
        Return the associated node.

        :return: node
        """
        nodes = super().all()
        if len(nodes) == 1:
            return nodes[0]
        if len(nodes) > 1:
            raise CardinalityViolation(self, len(nodes))

    def all(self):
        node = self.single()
        return [node] if node else []

    def connect(self, node, properties=None):
        """
        Connect to a node.

        :param node:
        :type: StructuredNode
        :param properties: relationship properties
        :type: dict
        :return: True / rel instance
        """
        if len(self):
            raise AttemptedCardinalityViolation(
                    "Node already has {0} can't connect more".format(self))
        else:
            return super().connect(node, properties)


class ZeroOrMore(RelationshipManager):
    """
    A relationship of zero or more nodes (the default)
    """
    description = "zero or more relationships"


class One(RelationshipManager):
    """
    A relationship to a single node
    """
    description = "one relationship"

    def single(self):
        """
        Return the associated node.

        :return: node
        """
        nodes = super().all()
        if len(nodes) == 1:
            return nodes[0]
        else:
            raise CardinalityViolation(self, len(nodes) or 'none')

    def all(self):
        """
        Return single node in an array

        :return: [node]
        """
        return [self.single()]

    def disconnect(self, node):
        raise AttemptedCardinalityViolation(
            "Cardinality one, cannot disconnect use reconnect."
        )

    def connect(self, node, properties=None):
        """
        Connect a node

        :param node:
        :param properties: relationship properties
        :return: True / rel instance
        """
        if not hasattr(self.source, 'id'):
            raise ValueError("Node has not been saved cannot connect!")
        if len(self):
            raise AttemptedCardinalityViolation(
                "Node already has one relationship"
            )
        else:
            return super().connect(node, properties)


class OneOrMore(RelationshipManager):
    """ A relationship to zero or more nodes. """
    description = "one or more relationships"

    def single(self):
        """
        Fetch one of the related nodes

        :return: Node
        """
        nodes = super().all()
        if nodes:
            return nodes[0]
        raise CardinalityViolation(self, 'none')

    def all(self):
        """
        Returns all related nodes.

        :return: [node1, node2...]
        """
        nodes = super().all()
        if nodes:
            return nodes
        raise CardinalityViolation(self, 'none')

    def disconnect(self, node):
        """
        Disconnect node
        :param node:
        :return:
        """
        if len(self) < 2:
            raise AttemptedCardinalityViolation("One or more expected")
        return super().disconnect(node)


# relationship definitions


class RelationshipDefinition(RelationshipDefinitionType):
    def __init__(self, relation_type, cls_name, direction, manager=RelationshipManager, model=None):
        self.module_name = sys._getframe(4).f_globals['__name__']
        if '__file__' in sys._getframe(4).f_globals:
            self.module_file = sys._getframe(4).f_globals['__file__']
        self._raw_class = cls_name
        self.manager = manager
        self.definition = {'direction': direction, 'model': model,
                           'relation_type': relation_type}

    # TODO this should at best be called only once
    # this should happen after all node models have been imported :-/
    # it may also be simplified with newer importlib capabilities
    # and introspective class properties
    def _lookup_node_class(self):
        if 'node_class' in self.definition:
            return

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


def _relationship_factory(cls_name, direction, rel_type, cardinality=None, model=None):
    if not isinstance(cls_name, (str, type)):
        raise ValueError('Expected class name or class got ' + repr(cls_name))

    if model and not issubclass(model, RelationshipType):
        raise ValueError('model must be a StructuredRel')
    return RelationshipDefinition(rel_type, cls_name, direction, cardinality, model)


def RelationshipTo(cls_name, rel_type, cardinality=ZeroOrMore, model=None):
    return _relationship_factory(cls_name, OUTGOING, rel_type, cardinality, model)


def RelationshipFrom(cls_name, rel_type, cardinality=ZeroOrMore, model=None):
    return _relationship_factory(cls_name, INCOMING, rel_type, cardinality, model)


def Relationship(cls_name, rel_type, cardinality=ZeroOrMore, model=None):
    return _relationship_factory(cls_name, EITHER, rel_type, cardinality, model)
