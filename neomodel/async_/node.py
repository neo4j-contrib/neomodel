"""
Node classes and metadata for the async neomodel module.
"""

from __future__ import annotations

import warnings
from itertools import combinations
from typing import TYPE_CHECKING, Any, Callable

from neo4j.graph import Node

from neomodel.async_.database import adb
from neomodel.async_.property_manager import AsyncPropertyManager
from neomodel.constants import STREAMING_WARNING
from neomodel.exceptions import DoesNotExist, NodeClassAlreadyDefined
from neomodel.hooks import hooks
from neomodel.properties import Property
from neomodel.util import _UnsavedNode, classproperty

if TYPE_CHECKING:
    from neomodel.async_.match import AsyncNodeSet


class NodeMeta(type):
    DoesNotExist: type[DoesNotExist]
    __required_properties__: tuple[str, ...]
    __all_properties__: tuple[tuple[str, Any], ...]
    __all_aliases__: tuple[tuple[str, Any], ...]
    __all_relationships__: tuple[tuple[str, Any], ...]
    __label__: str
    __optional_labels__: list[str]

    defined_properties: Callable[..., dict[str, Any]]

    def __new__(
        mcs: type, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> Any:
        namespace["DoesNotExist"] = type(name + "DoesNotExist", (DoesNotExist,), {})
        cls: NodeMeta = type.__new__(mcs, name, bases, namespace)
        cls.DoesNotExist._model_class = cls

        if hasattr(cls, "__abstract_node__"):
            delattr(cls, "__abstract_node__")
        else:
            if "deleted" in namespace:
                raise ValueError(
                    "Property name 'deleted' is not allowed as it conflicts with neomodel internals."
                )
            elif "id" in namespace:
                raise ValueError(
                    """
                        Property name 'id' is not allowed as it conflicts with neomodel internals.
                        Consider using 'uid' or 'identifier' as id is also a Neo4j internal.
                    """
                )
            elif "element_id" in namespace:
                raise ValueError(
                    """
                        Property name 'element_id' is not allowed as it conflicts with neomodel internals.
                        Consider using 'uid' or 'identifier' as element_id is also a Neo4j internal.
                    """
                )
            for key, value in (
                (x, y) for x, y in namespace.items() if isinstance(y, Property)
            ):
                value.name, value.owner = key, cls
                if hasattr(value, "setup") and callable(value.setup):
                    value.setup()

            # cache various groups of properies
            cls.__required_properties__ = tuple(
                name
                for name, property in cls.defined_properties(
                    aliases=False, rels=False
                ).items()
                if property.required or property.unique_index
            )
            cls.__all_properties__ = tuple(
                cls.defined_properties(aliases=False, rels=False).items()
            )
            cls.__all_aliases__ = tuple(
                cls.defined_properties(properties=False, rels=False).items()
            )
            cls.__all_relationships__ = tuple(
                cls.defined_properties(aliases=False, properties=False).items()
            )

            cls.__label__ = namespace.get("__label__", name)
            cls.__optional_labels__ = namespace.get("__optional_labels__", [])

            build_class_registry(cls)

        return cls


def build_class_registry(cls: Any) -> None:
    base_label_set = frozenset(cls.inherited_labels())
    optional_label_set = set(cls.inherited_optional_labels())

    # Construct all possible combinations of labels + optional labels
    possible_label_combinations = [
        frozenset(set(x).union(base_label_set))
        for i in range(1, len(optional_label_set) + 1)
        for x in combinations(optional_label_set, i)
    ]
    possible_label_combinations.append(base_label_set)

    for label_set in possible_label_combinations:
        if not hasattr(cls, "__target_databases__"):
            if label_set not in adb._NODE_CLASS_REGISTRY:
                adb._NODE_CLASS_REGISTRY[label_set] = cls
            else:
                raise NodeClassAlreadyDefined(
                    cls, adb._NODE_CLASS_REGISTRY, adb._DB_SPECIFIC_CLASS_REGISTRY
                )
        else:
            for database in cls.__target_databases__:
                if database not in adb._DB_SPECIFIC_CLASS_REGISTRY:
                    adb._DB_SPECIFIC_CLASS_REGISTRY[database] = {}
                if label_set not in adb._DB_SPECIFIC_CLASS_REGISTRY[database]:
                    adb._DB_SPECIFIC_CLASS_REGISTRY[database][label_set] = cls
                else:
                    raise NodeClassAlreadyDefined(
                        cls, adb._NODE_CLASS_REGISTRY, adb._DB_SPECIFIC_CLASS_REGISTRY
                    )


NodeBase: type = NodeMeta(
    "NodeBase", (AsyncPropertyManager,), {"__abstract_node__": True}
)


class AsyncStructuredNode(NodeBase):
    """
    Base class for all node definitions to inherit from.

    If you want to create your own abstract classes set:
        __abstract_node__ = True
    """

    # static properties

    __abstract_node__ = True

    # magic methods

    def __init__(self, *args: Any, **kwargs: Any):
        if "deleted" in kwargs:
            raise ValueError("deleted property is reserved for neomodel")

        for key, val in self.__all_relationships__:
            self.__dict__[key] = val.build_manager(self, key)

        super().__init__(*args, **kwargs)

    def __eq__(self, other: Any) -> bool:
        """
        Compare two node objects.
        If both nodes were saved to the database, compare them by their element_id.
        Otherwise, compare them using object id in memory.
        If `other` is not a node, always return False.
        """
        if not isinstance(other, (AsyncStructuredNode,)):
            return False
        if self.was_saved and other.was_saved:
            return self.element_id == other.element_id
        return id(self) == id(other)

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return repr(self.__properties__)

    # dynamic properties

    @classproperty
    def nodes(self) -> "AsyncNodeSet":
        """
        Returns a NodeSet object representing all nodes of the classes label
        :return: NodeSet
        :rtype: NodeSet
        """
        from neomodel.async_.match import AsyncNodeSet

        return AsyncNodeSet(self)

    @property
    def element_id(self) -> Any | None:
        if hasattr(self, "element_id_property"):
            return self.element_id_property
        return None

    # Version 4.4 support - id is deprecated in version 5.x
    @property
    def id(self) -> int:
        try:
            return int(self.element_id_property)
        except (TypeError, ValueError):
            raise ValueError(
                "id is deprecated in Neo4j version 5, please migrate to element_id. If you use the id in a Cypher query, replace id() by elementId()."
            )

    @property
    def was_saved(self) -> bool:
        """
        Shows status of node in the database. False, if node hasn't been saved yet, True otherwise.
        """
        return self.element_id is not None

    # methods

    @classmethod
    async def _build_merge_query(
        cls,
        merge_params: tuple[dict[str, Any], ...],
        update_existing: bool = False,
        lazy: bool = False,
        relationship: Any | None = None,
        rel_props: dict[str, Any] | None = None,
        merge_by: dict[str, str | list[str]] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """
        Get a tuple of a CYPHER query and a params dict for the specified MERGE query.

        :param merge_params: The target node match parameters, each node must have a "create" key and optional "update".
        :type merge_params: list of dict
        :param update_existing: True to update properties of existing nodes, default False to keep existing values.
        :type update_existing: bool
        :param lazy: False by default, specify True to get nodes with id only without the properties.
        :type lazy: bool
        :param relationship: Optional relationship to create when merging nodes.
        :type relationship: Any | None
        :param rel_props: Optional dictionary of relationship properties to deflate.
        :type rel_props: dict[str, Any] | None
        :param merge_by: Optional dict with 'label' and 'keys' to specify custom merge criteria.
                        'label' is optional and should be a string, 'keys' is a list of strings.
                        If 'label' is not provided, uses the node's inherited labels.
                        If 'keys' is not provided, uses the node's required properties as merge keys.
        :type merge_by: dict[str, str | list[str]] | None
        :return: tuple of query and params
        :rtype: tuple[str, dict[str, Any]]
        """
        query_params: dict[str, Any] = {"merge_params": merge_params}

        # Determine merge key and labels
        if merge_by:
            # Use custom merge keys
            merge_keys = merge_by["keys"]
            merge_labels = merge_by.get("label", ":".join(cls.inherited_labels()))

            n_merge_prm = ", ".join(f"{key}: params.create.{key}" for key in merge_keys)
        else:
            # Use default required properties
            merge_labels = ":".join(cls.inherited_labels())
            n_merge_prm = ", ".join(
                (
                    f"{getattr(cls, p).get_db_property_name(p)}: params.create.{getattr(cls, p).get_db_property_name(p)}"
                    for p in cls.__required_properties__
                )
            )

        n_merge = f"n:{merge_labels} {{{n_merge_prm}}}"
        if relationship is None:
            # create "simple" unwind query
            query = f"UNWIND $merge_params as params\n MERGE ({n_merge})\n "
        else:
            # validate relationship
            from neomodel.async_.relationship_manager import (
                deflate_relationship_properties,
                validate_relationship,
            )

            validate_relationship(relationship, rel_props)
            relation_type = relationship.definition.get("relation_type")

            from neomodel.async_.match import _rel_helper, _rel_merge_helper

            query_params["source_id"] = await adb.parse_element_id(
                relationship.source.element_id
            )
            query = f"MATCH (source:{relationship.source.__label__}) WHERE {await adb.get_id_method()}(source) = $source_id\n "
            query += "WITH source\n UNWIND $merge_params as params \n "
            query += "MERGE "
            if rel_props:
                rel_prop = deflate_relationship_properties(
                    relationship=relationship,
                    rel_props=rel_props,
                    query_params=query_params,
                )

                query += _rel_merge_helper(
                    lhs="source",
                    rhs=n_merge,
                    ident="r",
                    relation_type=relation_type,
                    direction=relationship.definition["direction"],
                    relation_properties=rel_prop,
                )
            else:
                query += _rel_helper(
                    lhs="source",
                    rhs=n_merge,
                    ident=None,
                    relation_type=relation_type,
                    direction=relationship.definition["direction"],
                )

        query += "ON CREATE SET n = params.create\n "
        # if update_existing, write properties on match as well
        if update_existing is True:
            query += "ON MATCH SET n += params.update\n"

        # close query
        if lazy:
            query += f"RETURN {await adb.get_id_method()}(n)"
        else:
            query += "RETURN n"

        return query, query_params

    @classmethod
    async def create(cls, *props: tuple, **kwargs: dict[str, Any]) -> list:
        """
        Call to CREATE with parameters map. A new instance will be created and saved.

        :param props: dict of properties to create the nodes.
        :type props: tuple
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :type: bool
        :rtype: list
        """

        if "streaming" in kwargs:
            warnings.warn(
                STREAMING_WARNING,
                category=DeprecationWarning,
                stacklevel=1,
            )

        lazy = kwargs.get("lazy", False)
        # create mapped query
        query = f"CREATE (n:{':'.join(cls.inherited_labels())} $create_params)"

        # close query
        if lazy:
            query += f" RETURN {await adb.get_id_method()}(n)"
        else:
            query += " RETURN n"

        results = []
        for item in [
            cls.deflate(p, obj=_UnsavedNode(), skip_empty=True) for p in props
        ]:
            node, _ = await adb.cypher_query(query, {"create_params": item})
            results.extend(node[0])

        nodes = [cls.inflate(node) for node in results]

        if not lazy and hasattr(cls, "post_create"):
            for node in nodes:
                node.post_create()

        return nodes

    @classmethod
    async def create_or_update(cls, *props: tuple, **kwargs: dict[str, Any]) -> list:
        """
        Call to MERGE with parameters map. A new instance will be created and saved if does not already exists,
        this is an atomic operation. If an instance already exists all optional properties specified will be updated.

        Note that the post_create hook isn't called after create_or_update

        :param props: List of dict arguments to get or create the entities with.
        :type props: tuple
        :param relationship: Optional, relationship to get/create on when new entity is created.
        :type relationship: Any | None
        :param lazy: False by default, specify True to get nodes with id only without the properties.
        :type lazy: bool
        :param merge_by: Optional dict with 'label' and 'keys' to specify custom merge criteria.
                        'label' is optional and should be a string, 'keys' is a list of strings.
                        If 'label' is not provided, uses the node's inherited labels.
                        If 'keys' is not provided, uses the node's required properties as merge keys.
        :type merge_by: dict[str, str | list[str]] | None
        :return: list of nodes
        :rtype: list
        """
        lazy: bool = bool(kwargs.get("lazy", False))
        relationship = kwargs.get("relationship")
        rel_props = kwargs.get("rel_props")
        merge_by = kwargs.get("merge_by")

        # build merge query, make sure to update only explicitly specified properties
        create_or_update_params = []
        for specified, deflated in [
            (p, cls.deflate(p, skip_empty=True)) for p in props
        ]:
            create_or_update_params.append(
                {
                    "create": deflated,
                    "update": {k: v for k, v in deflated.items() if k in specified},
                }
            )
        query, params = await cls._build_merge_query(
            tuple(create_or_update_params),
            update_existing=True,
            relationship=relationship,
            lazy=lazy,
            rel_props=rel_props,
            merge_by=merge_by,
        )

        if "streaming" in kwargs:
            warnings.warn(
                STREAMING_WARNING,
                category=DeprecationWarning,
                stacklevel=1,
            )

        # fetch and build instance for each result
        results = await adb.cypher_query(query, params)
        if lazy:
            return [r[0] for r in results[0]]
        else:
            return [cls.inflate(r[0]) for r in results[0]]

    async def cypher(
        self, query: str, params: dict[str, Any] | None = None
    ) -> tuple[list | None, tuple[str, ...] | None]:
        """
        Execute a cypher query with the param 'self' pre-populated with the nodes neo4j id.

        :param query: cypher query string
        :type: string
        :param params: query parameters
        :type: dict
        :return: tuple containing a list of query results, and the meta information as a tuple
        :rtype: tuple
        """
        self._pre_action_check("cypher")
        _params = params or {}
        if self.element_id is None:
            raise ValueError("Can't run cypher operation on unsaved node")
        element_id = await adb.parse_element_id(self.element_id)
        _params.update({"self": element_id})
        return await adb.cypher_query(query, _params)

    @hooks
    async def delete(self) -> bool:
        """
        Delete a node and its relationships

        :return: True
        """
        self._pre_action_check("delete")
        await self.cypher(
            f"MATCH (self) WHERE {await adb.get_id_method()}(self)=$self DETACH DELETE self"
        )
        delattr(self, "element_id_property")
        self.deleted = True
        return True

    @classmethod
    async def get_or_create(cls: Any, *props: tuple, **kwargs: dict[str, Any]) -> list:
        """
        Call to MERGE with parameters map. A new instance will be created and saved if does not already exist,
        this is an atomic operation.
        Parameters must contain all required properties, any non required properties with defaults will be generated.

        Note that the post_create hook isn't called after get_or_create

        :param props: Arguments to get_or_create as tuple of dict with property names and values to get or create
                      the entities with.
        :type props: tuple
        :param relationship: Optional, relationship to get/create on when new entity is created.
        :type relationship: Any | None
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :type lazy: bool
        :param merge_by: Optional dict with 'label' and 'keys' to specify custom merge criteria.
                        'label' is optional and should be a string, 'keys' is a list of strings.
                        If 'label' is not provided, uses the node's inherited labels.
                        If 'keys' is not provided, uses the node's required properties as merge keys.
        :type merge_by: dict[str, str | list[str]] | None
        :return: list of nodes
        :rtype: list
        """
        lazy = kwargs.get("lazy", False)
        relationship = kwargs.get("relationship")
        rel_props = kwargs.get("rel_props")
        merge_by = kwargs.get("merge_by")

        # build merge query
        get_or_create_params = [
            {"create": cls.deflate(p, skip_empty=True)} for p in props
        ]
        query, params = await cls._build_merge_query(
            tuple(get_or_create_params),
            relationship=relationship,
            lazy=lazy,
            rel_props=rel_props,
            merge_by=merge_by,
        )

        if "streaming" in kwargs:
            warnings.warn(
                STREAMING_WARNING,
                category=DeprecationWarning,
                stacklevel=1,
            )

        # fetch and build instance for each result
        results = await adb.cypher_query(query, params)
        if lazy:
            return [r[0] for r in results[0]]
        else:
            return [cls.inflate(r[0]) for r in results[0]]

    @classmethod
    def inflate(cls: Any, graph_entity: Node) -> Any:  # type: ignore[override]
        """
        Inflate a raw neo4j_driver node to a neomodel node
        :param graph_entity: node
        :return: node object
        """
        # support lazy loading
        if isinstance(graph_entity, str) or isinstance(graph_entity, int):
            snode = cls()
            snode.element_id_property = graph_entity
        else:
            snode = super().inflate(graph_entity)
            snode.element_id_property = graph_entity.element_id

        return snode

    @classmethod
    def inherited_labels(cls: Any) -> list[str]:
        """
        Return list of labels from nodes class hierarchy.

        :return: list
        """
        return [
            scls.__label__
            for scls in cls.mro()
            if hasattr(scls, "__label__") and not hasattr(scls, "__abstract_node__")
        ]

    @classmethod
    def inherited_optional_labels(cls: Any) -> list[str]:
        """
        Return list of optional labels from nodes class hierarchy.

        :return: list
        :rtype: list
        """
        return [
            label
            for scls in cls.mro()
            for label in getattr(scls, "__optional_labels__", [])
            if not hasattr(scls, "__abstract_node__")
        ]

    async def labels(self) -> list[str]:
        """
        Returns list of labels tied to the node from neo4j.

        :return: list of labels
        :rtype: list
        """
        self._pre_action_check("labels")
        result = await self.cypher(
            f"MATCH (n) WHERE {await adb.get_id_method()}(n)=$self RETURN labels(n)"
        )
        if result is None or result[0] is None:
            raise ValueError("Could not get labels, node may not exist")
        return result[0][0][0]

    def _pre_action_check(self, action: str) -> None:
        if hasattr(self, "deleted") and self.deleted:
            raise ValueError(
                f"{self.__class__.__name__}.{action}() attempted on deleted node"
            )
        if not hasattr(self, "element_id"):
            raise ValueError(
                f"{self.__class__.__name__}.{action}() attempted on unsaved node"
            )

    async def refresh(self) -> None:
        """
        Reload the node from neo4j
        """
        self._pre_action_check("refresh")
        if hasattr(self, "element_id"):
            results = await self.cypher(
                f"MATCH (n) WHERE {await adb.get_id_method()}(n)=$self RETURN n"
            )
            request = results[0]
            if not request or not request[0]:
                raise self.__class__.DoesNotExist("Can't refresh non existent node")
            node = self.inflate(request[0][0])
            for key, val in node.__properties__.items():
                setattr(self, key, val)
        else:
            raise ValueError("Can't refresh unsaved node")

    @hooks
    async def save(self) -> "AsyncStructuredNode":
        """
        Save the node to neo4j or raise an exception

        :return: the node instance
        """

        # create or update instance node
        if hasattr(self, "element_id_property"):
            # update
            params = self.deflate(self.__properties__, self)
            query = f"MATCH (n) WHERE {await adb.get_id_method()}(n)=$self\n"

            if params:
                query += "SET "
                query += ",\n".join([f"n.{key} = ${key}" for key in params])
                query += "\n"
            if self.inherited_labels():
                query += "\n".join(
                    [f"SET n:`{label}`" for label in self.inherited_labels()]
                )
            await self.cypher(query, params)
        elif hasattr(self, "deleted") and self.deleted:
            raise ValueError(
                f"{self.__class__.__name__}.save() attempted on deleted node"
            )
        else:  # create
            result = await self.create(self.__properties__)
            created_node = result[0]
            self.element_id_property = created_node.element_id
        return self
