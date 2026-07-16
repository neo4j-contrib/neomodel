"""
Node classes and metadata for the async neomodel module.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from neo4j.graph import Node

from neomodel.async_._registry import registry
from neomodel.async_.database import adb
from neomodel.async_.property_manager import AsyncPropertyManager
from neomodel.constants import STREAMING_WARNING
from neomodel.exceptions import DoesNotExist
from neomodel.hooks import hooks
from neomodel.properties import Property
from neomodel.util import _UnsavedNode, classproperty, deprecated, escape_label

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

            # Warn about mutual-exclusion groups with a single member: a group of
            # one excludes nothing, so it almost always signals a typo in the
            # exclusion_group name.
            exclusion_groups: dict[str, list[str]] = {}
            for rel_name, rel_def in cls.__all_relationships__:
                group = rel_def.definition.get("exclusion_group")
                if group:
                    exclusion_groups.setdefault(group, []).append(rel_name)
            for group, members in exclusion_groups.items():
                if len(members) < 2:
                    warnings.warn(
                        f"Mutual exclusion group '{group}' on {name} has a single "
                        f"member ({members[0]}); it excludes nothing. Did you mean "
                        f"to put another relationship in the same group?",
                        UserWarning,
                        stacklevel=2,
                    )

            cls.__label__ = namespace.get("__label__", name)
            cls.__optional_labels__ = namespace.get("__optional_labels__", [])

            # Defining a node class no longer pushes it into the registry; it just
            # invalidates the lazily-built scan index. The class is discovered from
            # the live hierarchy on the next resolution.
            registry.note_class_defined()

        return cls


@deprecated(
    "build_class_registry() is deprecated: node classes are discovered "
    "automatically from the live class hierarchy and no longer need registering."
)
def build_class_registry(cls: Any) -> None:
    registry.register(cls)


NodeBase: type = NodeMeta(
    "NodeBase", (AsyncPropertyManager,), {"__abstract_node__": True}
)

_T = TypeVar("_T", bound="AsyncStructuredNode")


class _NodesProperty:
    """Class-level descriptor backing ``MyNode.nodes``.

    Typing ``__get__`` with ``owner: type[_T]`` makes ``MyNode.nodes`` resolve to
    ``AsyncNodeSet[MyNode]`` for type checkers, so ``MyNode.nodes.get(...)`` is
    known to return ``MyNode`` (and iteration yields ``MyNode``). At runtime it
    behaves like the previous classproperty.
    """

    def __get__(self, instance: Any, owner: type[_T]) -> AsyncNodeSet[_T]:
        from neomodel.async_.match import AsyncNodeSet

        return AsyncNodeSet(owner)


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

    def __hash__(self) -> int:
        """
        Make node instances hashable (usable in sets and as dict keys).

        Defining ``__eq__`` above sets ``__hash__`` to None, which makes
        instances unhashable; this restores it consistently with ``__eq__``:
        saved nodes hash by their element_id (so two instances of the same
        database node hash equal), unsaved nodes hash by object identity.

        Note: a node's hash therefore changes when it is first saved, so do not
        rely on a node's membership in a set/dict across a save().
        """
        if self.was_saved:
            return hash(self.element_id)
        return hash(id(self))

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return repr(self.__properties__)

    # dynamic properties

    # Returns an AsyncNodeSet representing all nodes of the class's label.
    # See _NodesProperty for why this is a descriptor rather than a classproperty.
    nodes = _NodesProperty()

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

        n_merge = cls._build_merge_pattern(merge_by)

        if relationship is None:
            # create "simple" unwind query
            query = f"UNWIND $merge_params as params\n MERGE ({n_merge})\n "
        else:
            query = await cls._build_relationship_merge(
                n_merge, relationship, rel_props, query_params
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
    def _build_merge_pattern(cls, merge_by: dict[str, str | list[str]] | None) -> str:
        """Build the ``n:Labels {keys}`` node pattern used by the MERGE query."""
        if merge_by:
            label = merge_by.get("label")
            if label is not None and not isinstance(label, str):
                raise ValueError("merge_by 'label' must be a string")
            keys = merge_by["keys"]
            if not isinstance(keys, (list, tuple)):
                raise ValueError("merge_by 'keys' must be a list of strings")
            merge_labels = cls._merge_labels(label)
            merge_db_keys = cls._validated_merge_keys(list(keys))
        else:
            merge_labels = cls._merge_labels(None)
            merge_db_keys = [
                getattr(cls, p).get_db_property_name(p)
                for p in cls.__required_properties__
            ]

        n_merge_prm = ", ".join(
            f"`{key}`: params.create.`{key}`" for key in merge_db_keys
        )
        return f"n:{merge_labels} {{{n_merge_prm}}}"

    @classmethod
    def _merge_labels(cls, label: str | None) -> str:
        """Backtick-escape the merge label(s); fall back to inherited labels."""
        if label is not None:
            return escape_label(label)
        return ":".join(escape_label(lbl) for lbl in cls.inherited_labels())

    @classmethod
    def _validated_merge_keys(cls, keys: list[str]) -> list[str]:
        """Validate caller-supplied merge keys against defined properties.

        Keys come from the caller, so each must map to a defined property; the
        resolved db property names are later backtick-escaped to prevent Cypher
        injection.
        """
        defined = cls.defined_properties(aliases=False, rels=False)
        merge_db_keys = []
        for key in keys:
            if key not in defined:
                raise ValueError(
                    f"Invalid merge_by key '{key}': not a defined property of "
                    f"{cls.__name__}"
                )
            merge_db_keys.append(defined[key].get_db_property_name(key))
        return merge_db_keys

    @classmethod
    async def _build_relationship_merge(
        cls,
        n_merge: str,
        relationship: Any,
        rel_props: dict[str, Any] | None,
        query_params: dict[str, Any],
    ) -> str:
        """Build the MATCH/MERGE clause that connects the source node via a rel."""
        from neomodel.async_.relationship_manager import (
            deflate_relationship_properties,
            validate_relationship,
        )

        validate_relationship(relationship, rel_props)
        relation_type = relationship.definition.get("relation_type")
        direction = relationship.definition["direction"]

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
                direction=direction,
                relation_properties=rel_prop,
            )
        else:
            query += _rel_helper(
                lhs="source",
                rhs=n_merge,
                ident=None,
                relation_type=relation_type,
                direction=direction,
            )
        return query

    @classmethod
    @deprecated(
        "StructuredNode.create() is deprecated and will be removed in neomodel 8.0. "
        "Use MyNode.nodes.bulk_create(...) instead."
    )
    async def create(cls, *props: tuple, **kwargs: dict[str, Any]) -> list:
        """Deprecated alias for ``MyNode.nodes.bulk_create(...)``."""
        return await cls._bulk_create(*props, **kwargs)

    @classmethod
    async def _bulk_create(cls, *props: tuple, **kwargs: dict[str, Any]) -> list:
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

        create_params = [
            cls.deflate(p, obj=_UnsavedNode(), skip_empty=True) for p in props
        ]
        if not create_params:
            return []

        # Create all nodes in a single round-trip by unwinding the list of
        # property maps, rather than issuing one CREATE per node.
        query = (
            "UNWIND $create_params AS create_param\n"
            f"CREATE (n:{':'.join(cls.inherited_labels())})\n"
            "SET n = create_param\n"
        )

        # close query
        if lazy:
            query += f"RETURN {await adb.get_id_method()}(n)"
        else:
            query += "RETURN n"

        # UNWIND preserves order, so results line up with the input props.
        results, _ = await adb.cypher_query(query, {"create_params": create_params})

        nodes = [cls.inflate(row[0]) for row in results]

        if not lazy and hasattr(cls, "post_create"):
            for node in nodes:
                node.post_create()

        return nodes

    @classmethod
    @deprecated(
        "StructuredNode.create_or_update() is deprecated and will be removed in "
        "neomodel 8.0. Use MyNode.nodes.bulk_create_or_update(...) instead."
    )
    async def create_or_update(cls, *props: tuple, **kwargs: dict[str, Any]) -> list:
        """Deprecated alias for ``MyNode.nodes.bulk_create_or_update(...)``."""
        return await cls._bulk_create_or_update(*props, **kwargs)

    @classmethod
    async def _bulk_create_or_update(
        cls, *props: tuple, **kwargs: dict[str, Any]
    ) -> list:
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

    @classmethod
    async def bulk_save(
        cls, nodes: list[AsyncStructuredNode]
    ) -> list[AsyncStructuredNode]:
        """
        Save a list of nodes of this class in a bulk, minimising round-trips.

        New nodes (those never saved) are created in a single ``UNWIND ... CREATE``
        query, and already-saved nodes are updated in a single
        ``UNWIND ... MATCH ... SET`` query. So this issues at most two queries
        regardless of how many nodes are passed, rather than one round-trip per
        node as with calling ``save()`` in a loop.

        ``pre_save`` / ``post_save`` hooks are run on each node (as with
        ``save()``); ``post_create`` is not (use ``create()`` if you need it).
        All nodes must be instances of this class (they share its labels).

        :param nodes: the node instances to save
        :return: the same node instances, in the order given (created ones now
            carry their element_id)
        """
        nodes = list(nodes)
        if not nodes:
            return []

        for node in nodes:
            if hasattr(node, "deleted") and node.deleted:
                raise ValueError(
                    f"{cls.__name__}.bulk_save() attempted on deleted node"
                )
            if hasattr(node, "pre_save"):
                node.pre_save()

        to_create = [n for n in nodes if not hasattr(n, "element_id_property")]
        to_update = [n for n in nodes if hasattr(n, "element_id_property")]

        # Create the new nodes in a single round-trip (mirrors create()).
        if to_create:
            create_params = [
                cls.deflate(node.__properties__, obj=_UnsavedNode(), skip_empty=True)
                for node in to_create
            ]
            create_query = (
                "UNWIND $create_params AS create_param\n"
                f"CREATE (n:{':'.join(cls.inherited_labels())})\n"
                "SET n = create_param\n"
                "RETURN n"
            )
            results, _ = await adb.cypher_query(
                create_query, {"create_params": create_params}
            )
            # UNWIND preserves order, so results line up with to_create.
            for node, row in zip(to_create, results):
                node.element_id_property = cls.inflate(row[0]).element_id

        # Update the existing nodes in a single round-trip.
        if to_update:
            id_method = await adb.get_id_method()
            rows = [
                {
                    "eid": await adb.parse_element_id(node.element_id),
                    "props": cls.deflate(node.__properties__, node),
                }
                for node in to_update
            ]
            set_labels = "".join(
                f"SET n:{escape_label(label)}\n" for label in cls.inherited_labels()
            )
            update_query = (
                "UNWIND $rows AS row\n"
                f"MATCH (n) WHERE {id_method}(n) = row.eid\n"
                "SET n += row.props\n" + set_labels
            )
            await adb.cypher_query(update_query, {"rows": rows})

        for node in nodes:
            if hasattr(node, "post_save"):
                node.post_save()

        return nodes

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
    @deprecated(
        "StructuredNode.get_or_create() is deprecated and will be removed in "
        "neomodel 8.0. Use MyNode.nodes.bulk_get_or_create(...) instead."
    )
    async def get_or_create(cls: Any, *props: tuple, **kwargs: dict[str, Any]) -> list:
        """Deprecated alias for ``MyNode.nodes.bulk_get_or_create(...)``."""
        return await cls._bulk_get_or_create(*props, **kwargs)

    @classmethod
    async def _bulk_get_or_create(
        cls: Any, *props: tuple, **kwargs: dict[str, Any]
    ) -> list:
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
    def inflate(cls: Any, graph_entity: Node) -> Any:
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
        # ``element_id`` is a property that is always present on the class, so
        # ``hasattr`` would always be True; an unsaved node is one whose
        # element_id resolves to None.
        if self.element_id is None:
            raise ValueError(
                f"{self.__class__.__name__}.{action}() attempted on unsaved node"
            )

    async def refresh(self) -> None:
        """
        Reload the node from neo4j
        """
        self._pre_action_check("refresh")
        results = await self.cypher(
            f"MATCH (n) WHERE {await adb.get_id_method()}(n)=$self RETURN n"
        )
        request = results[0]
        if not request or not request[0]:
            raise self.__class__.DoesNotExist("Can't refresh non existent node")
        node = self.inflate(request[0][0])
        for key, val in node.__properties__.items():
            setattr(self, key, val)

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
                # Decouple the Cypher parameter name from the (potentially
                # untrusted) property key. SemiStructuredNode allows arbitrary
                # property keys to flow through deflate, so the key is
                # backtick-escaped to prevent Cypher injection, and a positional
                # parameter name is used for the value.
                set_clauses = []
                query_params = {}
                for index, (key, value) in enumerate(params.items()):
                    param_name = f"p{index}"
                    escaped_key = key.replace("`", "``")
                    set_clauses.append(f"n.`{escaped_key}` = ${param_name}")
                    query_params[param_name] = value
                query += "SET "
                query += ",\n".join(set_clauses)
                query += "\n"
            else:
                query_params = {}
            if self.inherited_labels():
                query += "\n".join(
                    [f"SET n:`{label}`" for label in self.inherited_labels()]
                )
            await self.cypher(query, query_params)
        elif hasattr(self, "deleted") and self.deleted:
            raise ValueError(
                f"{self.__class__.__name__}.save() attempted on deleted node"
            )
        else:  # create
            result = await self._bulk_create(self.__properties__)
            created_node = result[0]
            self.element_id_property = created_node.element_id
        return self
