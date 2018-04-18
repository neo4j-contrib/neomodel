from neomodel.exceptions import (
    AttemptedCardinalityViolation, CardinalityViolation
)
from neomodel.relationship_manager import (
    RelationshipManager, ZeroOrMore
)  #noqa: F401


class ZeroOrOne(RelationshipManager):
    """ A relationship to zero or one node. """
    description = "zero or one relationship"

    def single(self):
        """
        Return the associated node.

        :return: node
        """
        nodes = super(ZeroOrOne, self).all()
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
            return super(ZeroOrOne, self).connect(node, properties)


class OneOrMore(RelationshipManager):
    """ A relationship to zero or more nodes. """
    description = "one or more relationships"

    def single(self):
        """
        Fetch one of the related nodes

        :return: Node
        """
        nodes = super(OneOrMore, self).all()
        if nodes:
            return nodes[0]
        raise CardinalityViolation(self, 'none')

    def all(self):
        """
        Returns all related nodes.

        :return: [node1, node2...]
        """
        nodes = super(OneOrMore, self).all()
        if nodes:
            return nodes
        raise CardinalityViolation(self, 'none')

    def disconnect(self, node):
        """
        Disconnect node
        :param node:
        :return:
        """
        if super(OneOrMore, self).__len__() < 2:
            raise AttemptedCardinalityViolation("One or more expected")
        return super(OneOrMore, self).disconnect(node)


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
        nodes = super(One, self).all()
        if nodes:
            if len(nodes) == 1:
                return nodes[0]
            else:
                raise CardinalityViolation(self, len(nodes))
        else:
            raise CardinalityViolation(self, 'none')

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

    def disconnect_all(self):
        raise AttemptedCardinalityViolation(
            "Cardinality one, cannot disconnect_all use reconnect."
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
            return super(One, self).connect(node, properties)
