from typing import TYPE_CHECKING, Any, List, Optional

from neomodel.exceptions import (
    AttemptedCardinalityViolation,
    CardinalityViolation,
    MutualExclusionViolation,
)
from neomodel.sync_.relationship_manager import (  # pylint:disable=unused-import
    RelationshipManager,
    ZeroOrMore,
)

if TYPE_CHECKING:
    from neomodel import StructuredNode, StructuredRel


class ZeroOrOne(RelationshipManager):
    """A relationship to zero or one node."""

    description = "zero or one relationship"

    def _check_cardinality(
        self, node: "StructuredNode", soft_check: bool = False
    ) -> None:
        if self.__len__():
            if soft_check:
                print(
                    f"Cardinality violation detected : Node already has one relationship of type {self.definition['relation_type']}, should not connect more. Soft check is enabled so the relationship will be created. Note that strict check will be enabled by default in version 6.0"
                )
            else:
                raise AttemptedCardinalityViolation(
                    f"Node already has one relationship of type {self.definition['relation_type']}. Use reconnect() to replace the existing relationship."
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
        self, node: "StructuredNode", properties: Optional[dict[str, Any]] = None
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


class One(RelationshipManager):
    """
    A relationship to a single node
    """

    description = "one relationship"

    def _check_cardinality(
        self, node: "StructuredNode", soft_check: bool = False
    ) -> None:
        if self.__len__():
            if soft_check:
                print(
                    f"Cardinality violation detected : Node already has one relationship of type {self.definition['relation_type']}, should not connect more. Soft check is enabled so the relationship will be created. Note that strict check will be enabled by default in version 6.0"
                )
            else:
                raise AttemptedCardinalityViolation(
                    f"Node already has one relationship of type {self.definition['relation_type']}. Use reconnect() to replace the existing relationship."
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
        self, node: "StructuredNode", properties: Optional[dict[str, Any]] = None
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


class MutuallyExclusive(RelationshipManager):
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

    def _check_exclusivity(self) -> None:
        """
        Check if any of the mutually exclusive relationships are connected.
        Raises MutualExclusionViolation if a violation is found.
        """
        for rel_name in self.exclusion_group:
            if not hasattr(self.source, rel_name):
                continue

            rel_manager = getattr(self.source, rel_name)
            if rel_manager.__len__() > 0:
                raise MutualExclusionViolation(
                    f"Cannot connect to `{self}` when `{rel_name}` is already connected"
                )

    def connect(
        self, node: "StructuredNode", properties: Optional[dict[str, Any]] = None
    ) -> "StructuredRel":
        """
        Connect to a node, ensuring mutual exclusivity with other relationships.

        :param node: The node to connect to
        :param properties: Relationship properties
        :return: The created relationship
        """
        self._check_exclusivity()
        return super().connect(node, properties)
