from typing import TYPE_CHECKING, Any, List, Optional

from neomodel.async_.relationship_manager import (  # pylint:disable=unused-import
    AsyncRelationshipManager,
    AsyncZeroOrMore,
)
from neomodel.exceptions import (
    AttemptedCardinalityViolation,
    CardinalityViolation,
    MutualExclusionViolation,
)

if TYPE_CHECKING:
    from neomodel import AsyncStructuredNode, AsyncStructuredRel


class AsyncZeroOrOne(AsyncRelationshipManager):
    """A relationship to zero or one node."""

    description = "zero or one relationship"

    async def _check_cardinality(
        self, node: "AsyncStructuredNode", soft_check: bool = False
    ) -> None:
        if await self.get_len():
            if soft_check:
                print(
                    f"Cardinality violation detected : Node already has one relationship of type {self.definition['relation_type']}, should not connect more. Soft check is enabled so the relationship will be created. Note that strict check will be enabled by default in version 6.0"
                )
            else:
                raise AttemptedCardinalityViolation(
                    f"Node already has one relationship of type {self.definition['relation_type']}. Use reconnect() to replace the existing relationship."
                )

    async def single(self) -> Optional["AsyncStructuredNode"]:
        """
        Return the associated node.

        :return: node
        """
        nodes = await super().all()
        if len(nodes) == 1:
            return nodes[0]
        if len(nodes) > 1:
            raise CardinalityViolation(self, len(nodes))
        return None

    async def all(self) -> list["AsyncStructuredNode"]:
        node = await self.single()
        return [node] if node else []

    async def connect(
        self, node: "AsyncStructuredNode", properties: Optional[dict[str, Any]] = None
    ) -> "AsyncStructuredRel":
        """
        Connect to a node.

        :param node:
        :type: StructuredNode
        :param properties: relationship properties
        :type: dict
        :return: True / rel instance
        """
        return await super().connect(node, properties)


class AsyncOneOrMore(AsyncRelationshipManager):
    """A relationship to zero or more nodes."""

    description = "one or more relationships"

    async def single(self) -> "AsyncStructuredNode":
        """
        Fetch one of the related nodes

        :return: Node
        """
        nodes = await super().all()
        if nodes:
            return nodes[0]
        raise CardinalityViolation(self, "none")

    async def all(self) -> list["AsyncStructuredNode"]:
        """
        Returns all related nodes.

        :return: [node1, node2...]
        """
        nodes = await super().all()
        if nodes:
            return nodes
        raise CardinalityViolation(self, "none")

    async def disconnect(self, node: "AsyncStructuredNode") -> None:
        """
        Disconnect node
        :param node:
        :return:
        """
        if await super().get_len() < 2:
            raise AttemptedCardinalityViolation("One or more expected")
        return await super().disconnect(node)


class AsyncOne(AsyncRelationshipManager):
    """
    A relationship to a single node
    """

    description = "one relationship"

    async def _check_cardinality(
        self, node: "AsyncStructuredNode", soft_check: bool = False
    ) -> None:
        if await self.get_len():
            if soft_check:
                print(
                    f"Cardinality violation detected : Node already has one relationship of type {self.definition['relation_type']}, should not connect more. Soft check is enabled so the relationship will be created. Note that strict check will be enabled by default in version 6.0"
                )
            else:
                raise AttemptedCardinalityViolation(
                    f"Node already has one relationship of type {self.definition['relation_type']}. Use reconnect() to replace the existing relationship."
                )

    async def single(self) -> "AsyncStructuredNode":
        """
        Return the associated node.

        :return: node
        """
        nodes = await super().all()
        if nodes:
            if len(nodes) == 1:
                return nodes[0]
            raise CardinalityViolation(self, len(nodes))
        raise CardinalityViolation(self, "none")

    async def all(self) -> list["AsyncStructuredNode"]:
        """
        Return single node in an array

        :return: [node]
        """
        return [await self.single()]

    async def disconnect(self, node: "AsyncStructuredNode") -> None:
        raise AttemptedCardinalityViolation(
            "Cardinality one, cannot disconnect use reconnect."
        )

    async def disconnect_all(self) -> None:
        raise AttemptedCardinalityViolation(
            "Cardinality one, cannot disconnect_all use reconnect."
        )

    async def connect(
        self, node: "AsyncStructuredNode", properties: Optional[dict[str, Any]] = None
    ) -> "AsyncStructuredRel":
        """
        Connect a node

        :param node:
        :param properties: relationship properties
        :return: True / rel instance
        """
        if not hasattr(self.source, "element_id") or self.source.element_id is None:
            raise ValueError("Node has not been saved cannot connect!")
        return await super().connect(node, properties)


class AsyncMutuallyExclusive(AsyncRelationshipManager):
    """
    A relationship that is mutually exclusive with other relationships.

    This cardinality constraint ensures that if this relationship is connected,
    other relationships in the exclusion group cannot be connected, and vice versa.
    """

    description = "mutually exclusive relationship"
    exclusion_group: List[str] = []

    def __init__(self, source: Any, key: str, definition: dict):
        super().__init__(source, key, definition)
        # Initialize exclusion_group from definition if provided
        if "exclusion_group" in definition:
            self.exclusion_group = definition["exclusion_group"]

    async def _check_exclusivity(self) -> None:
        """
        Check if any of the mutually exclusive relationships are connected.
        Raises MutualExclusionViolation if a violation is found.
        """
        for rel_name in self.exclusion_group:
            if not hasattr(self.source, rel_name):
                continue

            rel_manager = getattr(self.source, rel_name)
            if await rel_manager.get_len() > 0:
                raise MutualExclusionViolation(
                    f"Cannot connect to `{self}` when `{rel_name}` is already connected"
                )

    async def connect(
        self, node: "AsyncStructuredNode", properties: Optional[dict[str, Any]] = None
    ) -> "AsyncStructuredRel":
        """
        Connect to a node, ensuring mutual exclusivity with other relationships.

        :param node: The node to connect to
        :param properties: Relationship properties
        :return: The created relationship
        """
        await self._check_exclusivity()
        return await super().connect(node, properties)
