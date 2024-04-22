from neomodel.async_.core import AsyncStructuredNode
from neomodel.exceptions import DeflateConflict, InflateConflict
from neomodel.util import get_graph_entity_properties


class AsyncSemiStructuredNode(AsyncStructuredNode):
    """
    A base class allowing properties to be stored on a node that aren't
    specified in its definition. Conflicting properties are signaled with the
    :class:`DeflateConflict` exception::

        class Person(AsyncSemiStructuredNode):
            name = StringProperty()
            age = IntegerProperty()

            def hello(self):
                print("Hi my names " + self.name)

        tim = await Person(name='Tim', age=8, weight=11).save()
        tim.hello = "Hi"
        await tim.save() # DeflateConflict
    """

    __abstract_node__ = True

    @classmethod
    def inflate(cls, node):
        # Inflate all properties registered in the class definition
        snode = super().inflate(node)

        # Node can be a string or int for lazy loading (See StructuredNode.inflate). In that case, `node` has nothing
        # that can be unpacked further.
        if not hasattr(node, "items"):
            return snode

        # Inflate all extra properties not registered in the class definition
        registered_db_property_names = {
            property.get_db_property_name(name)
            for name, property in cls.defined_properties(
                aliases=False, rels=False
            ).items()
        }
        extra_keys = node.keys() - registered_db_property_names
        for extra_key in extra_keys:
            value = node[extra_key]
            if hasattr(cls, extra_key):
                raise InflateConflict(cls, extra_key, value, snode.element_id)
            setattr(snode, extra_key, value)

        return snode

    @classmethod
    def deflate(cls, node_props, obj=None, skip_empty=False):
        # Deflate all properties registered in the class definition
        deflated = super().deflate(node_props, obj, skip_empty=skip_empty)

        # Deflate all extra properties not registered in the class definition
        registered_names = cls.defined_properties(aliases=False, rels=False).keys()
        extra_keys = node_props.keys() - registered_names
        for extra_key in extra_keys:
            value = node_props[extra_key]
            if hasattr(cls, extra_key):
                raise DeflateConflict(
                    cls, extra_key, value, node_props.get("element_id")
                )
            deflated[extra_key] = node_props[extra_key]

        return deflated
