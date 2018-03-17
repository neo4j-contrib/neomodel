import warnings
from functools import wraps

from neomodel import config
from neomodel.bases import PropertyManager, PropertyManagerMeta
from neomodel.db import client, install_labels
from neomodel.exceptions import (
    DoesNotExist, NodeIsDeletedError, UnsavedNodeError
)
from neomodel.hooks import hooks
from neomodel.match import OUTGOING, NodeSet, _rel_helper
from neomodel.types import NodeType, RelationshipDefinitionType
from neomodel.util import (
    classproperty, is_abstract_node_model,
    get_members_of_type, registries, _UnsavedNode,
)


class NodeMeta(PropertyManagerMeta):
    def __new__(mcs, name, bases, namespace):
        namespace.update({
            '__label__': namespace.get('__label__', name),
            'DoesNotExist': type(name + 'DoesNotExist', (DoesNotExist,), {}),
        })

        cls = super().__new__(mcs, name, bases, namespace)

        # needed by Python < 3.5 for unpickling DoesNotExist objects:
        cls.DoesNotExist._model_class = cls

        if len(cls.__mro__) <= 5:  # ignore all bases up to StructuredNode
            pass
        elif not is_abstract_node_model(cls):
            registries.concrete_node_models.add(cls)

        cls.__relationship_definitions__ = \
            get_members_of_type(cls, RelationshipDefinitionType)

        if any(x.startswith('__') for x
               in cls.__relationship_definitions__):
            raise ValueError("Relationships' names must not start with '__'.")

        if config.AUTO_INSTALL_LABELS:
            install_labels(cls)

        return cls


def ensure_node_exists_in_db(method):
    """ Decorates node methods that require a node record in the database.  """
    deleted_msg = method.__qualname__ + '{}() attempted on deleted node.'
    unsaved_msg = method.__qualname__ + '{}() attempted on unsaved node.'

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if getattr(self, '__deleted__', False):
            raise NodeIsDeletedError(deleted_msg)
        if not hasattr(self, 'id'):
            raise UnsavedNodeError(unsaved_msg)
        return method(self, *args, **kwargs)
    return wrapper


class StructuredNode(PropertyManager, NodeType, metaclass=NodeMeta):
    """
    Base class for all node definitions to inherit from.

    If you want to create your own abstract classes set:
        __abstract_node__ = True
    """

    # static properties

    __abstract_node__ = True

    # magic methods

    def __init__(self, *args, **kwargs):
        for name, definition in self.__relationship_definitions__.items():
            setattr(self, name, definition.build_manager(self, name))

        super().__init__(*args, **kwargs)

    def __eq__(self, other):
        if not isinstance(other, NodeType):
            return False
        if hasattr(self, 'id') and hasattr(other, 'id'):
            return self.id == other.id
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return '<{}: {}>'.format(self.__class__.__name__, self)

    def __str__(self):
        return repr(self.__properties__)

    # dynamic properties

    @classproperty
    def nodes(cls):
        """
        Returns a NodeSet object representing all nodes of the classes label
        :return: NodeSet
        :rtype: NodeSet
        """
        return NodeSet(cls)

    # methods

    @classmethod
    def _build_merge_query(cls, merge_params, update_existing=False, lazy=False, relationship=None):
        """
        Get a tuple of a CYPHER query and a params dict for the specified MERGE query.

        :param merge_params: The target node match parameters, each node must have a "create" key and optional "update".
        :type merge_params: list of dict
        :param update_existing: True to update properties of existing nodes, default False to keep existing values.
        :type update_existing: bool
        :rtype: tuple
        """
        query_params = dict(merge_params=merge_params)
        n_merge = "n:{} {{{}}}".format(':'.join(cls.inherited_labels()),
                                         ", ".join("{0}: params.create.{0}".format(p) for p in cls.__required_properties__))
        if relationship is None:
            # create "simple" unwind query
            query = "UNWIND {{merge_params}} as params\n MERGE ({})\n ".format(n_merge)
        else:
            # validate relationship
            if not isinstance(relationship.source, NodeType):
                raise TypeError("relationship source [%s] is not a NodeType" % repr(relationship.source))
            relation_type = relationship.definition.get('relation_type')
            if not relation_type:
                raise ValueError('No relation_type is specified on provided relationship')

            query_params["source_id"] = relationship.source.id
            query = "MATCH (source:{}) WHERE ID(source) = {{source_id}}\n ".format(relationship.source.__label__)
            query += "WITH source\n UNWIND {merge_params} as params \n "
            query += "MERGE "
            query += _rel_helper(rhs='source', lhs=n_merge, ident=None,
                                 relation_type=relation_type, direction=OUTGOING)

        query += "ON CREATE SET n = params.create\n "
        # if update_existing, write properties on match as well
        if update_existing is True:
            query += "ON MATCH SET n += params.update\n"

        # close query
        if lazy:
            query += "RETURN id(n)"
        else:
            query += "RETURN n"

        return query, query_params

    @classmethod
    def create(cls, *props, **kwargs):
        """
        Call to CREATE with parameters map. A new instance will be created and saved.

        :param props: dict of properties to create the nodes.
        :type props: tuple
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :type: bool
        :rtype: list
        """

        if 'streaming' in kwargs:
            warnings.warn('streaming is not supported by bolt, please remove the kwarg',
                          category=UserWarning, stacklevel=1)

        lazy = kwargs.get('lazy', False)
        # create mapped query
        query = "CREATE (n:{} {{create_params}})".format(':'.join(cls.inherited_labels()))

        # close query
        if lazy:
            query += " RETURN id(n)"
        else:
            query += " RETURN n"

        results = []
        for item in [cls.deflate(p, obj=_UnsavedNode(), skip_empty=True) for p in props]:
            node, _ = client.cypher_query(query, {'create_params': item})
            results.extend(node[0])

        nodes = [cls.inflate(node) for node in results]

        if not lazy and hasattr(cls, 'post_create'):
            for node in nodes:
                node.post_create()

        return nodes

    @classmethod
    def create_or_update(cls, *props, **kwargs):
        """
        Call to MERGE with parameters map. A new instance will be created and saved if does not already exists,
        this is an atomic operation. If an instance already exists all optional properties specified will be updated.

        Note that the post_create hook isn't called after get_or_create

        :param props: List of dict arguments to get or create the entities with.
        :type props: tuple
        :param relationship: Optional, relationship to get/create on when new entity is created.
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :rtype: list
        """
        lazy = kwargs.get('lazy', False)
        relationship = kwargs.get('relationship')

        # build merge query, make sure to update only explicitly specified properties
        create_or_update_params = []
        for specified, deflated in [(p, cls.deflate(p, skip_empty=True)) for p in props]:
            create_or_update_params.append({
                "create": deflated,
                "update": {k: v for k, v in deflated.items() if k in specified}
            })
        query, params = cls._build_merge_query(create_or_update_params, update_existing=True, relationship=relationship,
                                               lazy=lazy)

        if 'streaming' in kwargs:
            warnings.warn('streaming is not supported by bolt, please remove the kwarg',
                          category=UserWarning, stacklevel=1)

        # fetch and build instance for each result
        results = client.cypher_query(query, params)
        return [cls.inflate(r[0]) for r in results[0]]

    @ensure_node_exists_in_db
    def cypher(self, query, params=None):
        """
        Execute a cypher query with the param 'self' pre-populated with the nodes neo4j id.

        :param query: cypher query string
        :type: string
        :param params: query parameters
        :type: dict
        :return: list containing query results
        :rtype: list
        """
        params = params or {}
        params.update({'self': self.id})
        return client.cypher_query(query, params)

    @hooks
    @ensure_node_exists_in_db
    def delete(self):
        """
        Delete a node and it's relationships

        :return: True
        """
        self.cypher("MATCH (self) WHERE id(self)={self} "
                    "OPTIONAL MATCH (self)-[r]-()"
                    " DELETE r, self")
        delattr(self, 'id')
        self.__deleted__ = True
        return True

    @classmethod
    def get_or_create(cls, *props, **kwargs):
        """
        Call to MERGE with parameters map. A new instance will be created and saved if does not already exists,
        this is an atomic operation.
        Parameters must contain all required properties, any non required properties with defaults will be generated.

        Note that the post_create hook isn't called after get_or_create

        :param props: dict of properties to get or create the entities with.
        :type props: tuple
        :param relationship: Optional, relationship to get/create on when new entity is created.
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :rtype: list
        """
        lazy = kwargs.get('lazy', False)
        relationship = kwargs.get('relationship')

        # build merge query
        get_or_create_params = [{"create": cls.deflate(p, skip_empty=True)} for p in props]
        query, params = cls._build_merge_query(get_or_create_params, relationship=relationship, lazy=lazy)

        if 'streaming' in kwargs:
            warnings.warn('streaming is not supported by bolt, please remove the kwarg',
                          category=UserWarning, stacklevel=1)

        # fetch and build instance for each result
        results = client.cypher_query(query, params)
        return [cls.inflate(r[0]) for r in results[0]]

    @classmethod
    def inflate(cls, node):
        """
        Inflate a raw neo4j_driver node to a neomodel node
        :param node:
        :return: node object
        """
        # support lazy loading
        if isinstance(node, int):
            snode = cls()
            snode.id = node
        else:
            props = {}
            for name, definition in cls.__property_definitions__.items():
                # map property name from database to object property
                db_property = definition.db_property or name

                if db_property in node.properties:
                    props[name] = definition.inflate(node.properties[db_property], node)
                elif definition.has_default:
                    props[name] = definition.default_value()
                else:
                    props[name] = None

            snode = cls(**props)
            snode.id = node.id

        return snode

    @classmethod
    def inherited_labels(cls):
        """
        Return list of labels from nodes class hierarchy.

        :return: list
        """
        # FIXME isn't this static?
        return tuple(
            baseclass.__label__ for baseclass in cls.__mro__
            if hasattr(baseclass, '__label__')
            and not is_abstract_node_model(baseclass)
        )

    @ensure_node_exists_in_db
    def labels(self):
        """
        Returns list of labels tied to the node from neo4j.

        :return: list of labels
        :rtype: list
        """
        return self.cypher("MATCH (n) WHERE id(n)={self} "
                           "RETURN labels(n)")[0][0][0]

    @ensure_node_exists_in_db
    def _noop(self):
        pass

    @ensure_node_exists_in_db
    def refresh(self):
        """
        Reload the node from neo4j
        """
        if hasattr(self, 'id'):
            node = self.inflate(self.cypher("MATCH (n) WHERE id(n)={self}"
                                            " RETURN n")[0][0][0])
            for key, val in node.__properties__.items():
                setattr(self, key, val)
        else:
            raise ValueError("Can't refresh unsaved node")

    @hooks
    def save(self):
        """
        Save the node to neo4j or raise an exception

        :return: the node instance
        """

        # create or update instance node
        if hasattr(self, 'id'):
            # update
            params = self.deflate(self.__properties__, self)
            query = "MATCH (n) WHERE id(n)={self} \n"
            query += "\n".join(["SET n.{} = {{{}}}".format(key, key) + "\n"
                                for key in params.keys()])
            for label in self.inherited_labels():
                query += "SET n:`{}`\n".format(label)
            self.cypher(query, params)
        elif getattr(self, '__deleted__', False):
            raise NodeIsDeletedError("{}.save() attempted on deleted node".format(
                self.__class__.__name__))
        else:  # create
            self.id = self.create(self.__properties__)[0].id
        return self
