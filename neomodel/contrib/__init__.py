

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
    """

    def __init__(self, *args, **kwargs):
        try:
            super(Hierarchical, self).__init__(*args, **kwargs)
        except TypeError:
            super(Hierarchical, self).__init__()
        self.__parent__ = None
        for key, value in kwargs.iteritems():
            if key == "__parent__":
                self.__parent__ = value
        if hasattr(self, "post_create_hooks"):
            def hook(node):
                if self.__parent__ and hasattr(self, "__node__"):
                    rel_type = self.__class__.__name__.upper()
                    node.client.create(
                        (self.__parent__.__node__, rel_type, self.__node__, {"__child__": True})
                    )
            self.post_create_hooks.append(hook)

    def parent(self):
        return self.__parent__

    def children(self, cls):
        if hasattr(self, "__node__"):
            rel_type = cls.__name__.upper()
            child_nodes = [
                rel.end_node
                for rel in self.__node__.get_relationships(1, rel_type)
                if rel["__child__"]
            ]
            return [cls.inflate(node) for node in child_nodes]
        else:
            return []
