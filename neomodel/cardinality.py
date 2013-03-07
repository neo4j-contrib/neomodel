from .relationship import RelationshipManager, ZeroOrMore


class ZeroOrOne(RelationshipManager):
    description = "zero or one relationship"

    def single(self):
        nodes = super(ZeroOrOne, self).all()
        if not nodes:
            return
        if len(nodes) == 1:
            return nodes[0]
        if len(nodes) > 1:
            raise CardinalityViolation(self, len(nodes))

    def all(self):
        node = self.single()
        return [node] if node else []

    def connect(self, obj):
        if self.origin.__node__.has_relationship(self.direction, self.relation_type):
            raise AttemptedCardinalityViolation("Node already has one relationship")
        else:
            return super(ZeroOrOne, self).connect(obj)


class OneOrMore(RelationshipManager):
    description = "one or more relationships"

    def single(self):
        nodes = super(OneOrMore, self).all()
        if nodes:
            return nodes[0]
        raise CardinalityViolation(self, 'none')

    def all(self):
        nodes = super(OneOrMore, self).all()
        if nodes:
            return nodes
        raise CardinalityViolation(self, 'none')

    def disconnect(self, obj):
        if len(self.origin.__node__.get_related_nodes(self.direction, self.relation_type)) < 2:
            raise AttemptedCardinalityViolation("One or more expected")
        return super(OneOrMore, self).disconnect(obj)


class One(RelationshipManager):
    description = "one relationship"

    def single(self):
        nodes = super(One, self).all()
        if nodes:
            if len(nodes) == 1:
                return nodes[0]
            else:
                raise CardinalityViolation(self, len(nodes))
        else:
            raise CardinalityViolation(self, 'none')

    def all(self):
        return [self.single()]

    def disconnect(self, obj):
        raise AttemptedCardinalityViolation("Cardinality one, cannot disconnect use rerelate")

    def connect(self, obj):
        if not self.origin.__node__:
            raise Exception("Node has not been saved cannot connect!")
        if self.origin.__node__.has_relationship(self.direction, self.relation_type):
            raise AttemptedCardinalityViolation("Node already has one relationship")
        else:
            return super(One, self).connect(obj)


class AttemptedCardinalityViolation(Exception):
    pass


class CardinalityViolation(Exception):
    def __init__(self, rel_manager, actual):
        self.rel_manager = str(rel_manager)
        self.actual = str(actual)

    def __str__(self):
        return "CardinalityViolation: Expected {0} got {1}".format(self.rel_manager, self.actual)
