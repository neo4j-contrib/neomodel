from typing import TYPE_CHECKING, Any, Optional

from neomodel.config import get_config
from neomodel.exceptions import AttemptedCardinalityViolation, CardinalityViolation
from neomodel.sync_.relationship_manager import (  # pylint:disable=unused-import
    RelationshipManager,
    ZeroOrMore,
)

if TYPE_CHECKING:
    from neomodel import StructuredNode, StructuredRel


class ZeroOrOne(RelationshipManager):
    """A relationship to zero or one node."""

    description = "zero or one relationship"

    def check_cardinality(self, node: "StructuredNode") -> None:
        if self.__len__():
            detailed_description = str(self)
            if get_config().soft_cardinality_check:
                print(
                    f"Cardinality violation detected : Node already has {detailed_description}, should not connect more. Soft check is enabled so the relationship will be created."
                )
            else:
                raise AttemptedCardinalityViolation(
                    f"Node already has {detailed_description}. Use reconnect() to replace the existing relationship."
                )

    def single(self) -> Optional["StructuredNode"]:
        """
        Return the associated node.

        :return: node
        """
        nodes = super().all()
        if len(nodes) == 1:
            return nodes[0]
        if len(nodes) > 1:
            raise CardinalityViolation(self, len(nodes))
        return None

    def all(self) -> list["StructuredNode"]:
        node = self.single()
        return [node] if node else []

    def connect(
        self, node: "StructuredNode", properties: dict[str, Any] | None = None
    ) -> "StructuredRel":
        """
        Connect to a node.

        :param node:
        :type: StructuredNode
        :param properties: relationship properties
        :type: dict
        :return: True / rel instance
        """
        return super().connect(node, properties)


class OneOrMore(RelationshipManager):
    """A relationship to zero or more nodes."""

    description = "one or more relationships"

    def single(self) -> "StructuredNode":
        """
        Fetch one of the related nodes

        :return: Node
        """
        nodes = super().all()
        if nodes:
            return nodes[0]
        raise CardinalityViolation(self, "none")

    def all(self) -> list["StructuredNode"]:
        """
        Returns all related nodes.

        :return: [node1, node2...]
        """
        nodes = super().all()
        if nodes:
            return nodes
        raise CardinalityViolation(self, "none")

    def disconnect(self, node: "StructuredNode") -> None:
        """
        Disconnect node
        :param node:
        :return:
        """
        if super().__len__() < 2:
            raise AttemptedCardinalityViolation("One or more expected")
        return super().disconnect(node)

    def disconnect_all(self) -> None:
        raise AttemptedCardinalityViolation(
            "Cardinality one or more, cannot disconnect_all use reconnect."
        )


class One(RelationshipManager):
    """
    A relationship to a single node
    """

    description = "one relationship"

    def check_cardinality(self, node: "StructuredNode") -> None:
        if self.__len__():
            detailed_description = str(self)
            if get_config().soft_cardinality_check:
                print(
                    f"Cardinality violation detected : Node already has {detailed_description}, should not connect more. Soft check is enabled so the relationship will be created."
                )
            else:
                raise AttemptedCardinalityViolation(
                    f"Node already has {detailed_description}. Use reconnect() to replace the existing relationship."
                )

    def single(self) -> "StructuredNode":
        """
        Return the associated node.

        :return: node
        """
        nodes = super().all()
        if nodes:
            if len(nodes) == 1:
                return nodes[0]
            raise CardinalityViolation(self, len(nodes))
        raise CardinalityViolation(self, "none")

    def all(self) -> list["StructuredNode"]:
        """
        Return single node in an array

        :return: [node]
        """
        return [self.single()]

    def disconnect(self, node: "StructuredNode") -> None:
        raise AttemptedCardinalityViolation(
            "Cardinality one, cannot disconnect use reconnect."
        )

    def disconnect_all(self) -> None:
        raise AttemptedCardinalityViolation(
            "Cardinality one, cannot disconnect_all use reconnect."
        )

    def connect(
        self, node: "StructuredNode", properties: dict[str, Any] | None = None
    ) -> "StructuredRel":
        """
        Connect a node

        :param node:
        :param properties: relationship properties
        :return: True / rel instance
        """
        if not hasattr(self.source, "element_id") or self.source.element_id is None:
            raise ValueError("Node has not been saved cannot connect!")
        return super().connect(node, properties)
