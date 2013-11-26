from ..core import StructuredNode


class Hierarchical(object):
    """ The Hierarchical mixin provides parent-child context for
        StructuredNodes. On construction of a new object, the `__parent__`
        argument should contain another `StructuredNode` and is used to
        build a relationship `(P)-[R:T]->(C)` with the following parameters:

        - `P` - parent node
        - `C` - child node (this StructuredNode instance)
        - `R` - the parent->child relationship with `__child__` set to `True`
        - `T` - the relationship type determined by the class of this node

        This mixin can therefore be used as follows::

            class Country(Hierarchical, StructuredNode):
                code = StringProperty(unique_index=True)
                name = StringProperty()

            class Nationality(Hierarchical, StructuredNode):
                code = StringProperty(unique_index=True)
                name = StringProperty()

            cy = Country(code="CY", name="Cyprus").save()
            greek_cypriot = Nationality(__parent__=cy, code="CY-GR", name="Greek Cypriot").save()

        The code above will create relationships thus:

            (CY {"code":"CY","name":"Cyprus"})
            (CY_GR {"code":"CY-GR","name":"Greek Cypriot"})
            (CY)-[:NATIONALITY {"__child__":True}]->(CY_GR)

        Note also that the `Hierarchical` constructor registers a
        post_create_hook with the instance which allows this relationship
        to be created.

        :ivar __parent__: parent object according to defined hierarchy
    """

    def __init__(self, *args, **kwargs):
        try:
            super(Hierarchical, self).__init__(*args, **kwargs)
        except TypeError:
            super(Hierarchical, self).__init__()
        self.__parent__ = None
        for key, value in kwargs.items():
            if key == "__parent__":
                self.__parent__ = value

    def post_create(self):
        """ Called by StructuredNode class on creation of new instance. Will
            build relationship from parent to child (this) node.
        """
        if self.__parent__ and isinstance(self, StructuredNode):
            self.client.create(
                (self.__parent__.__node__, self.relationship_type(), self.__node__, {"__child__": True})
            )

    def parent(self):
        return self.__parent__

    def children(self, cls):
        if isinstance(self, StructuredNode):
            child_nodes = [
                rel.end_node
                for rel in self.__node__.match_outgoing(cls.relationship_type())
                if rel["__child__"]
            ]
            return [cls.inflate(node) for node in child_nodes]
        else:
            return []
