from typing import TYPE_CHECKING, Any, Optional

from neomodel.async_.relationship_manager import (  # pylint:disable=unused-import
    AsyncRelationshipManager,
    AsyncZeroOrMore,
)
from neomodel.exceptions import AttemptedCardinalityViolation, CardinalityViolation

if TYPE_CHECKING:
    from neomodel import AsyncStructuredNode, AsyncStructuredRel


class AsyncZeroOrOne(AsyncRelationshipManager):
    """A relationship to zero or one node."""

    description = "zero or one relationship"

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
        if await super().get_len():
            raise AttemptedCardinalityViolation(
                f"Node already has {self} can't connect more"
            )
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
        if await super().get_len():
            raise AttemptedCardinalityViolation("Node already has one relationship")
        return await super().connect(node, properties)
