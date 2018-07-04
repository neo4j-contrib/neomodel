from neomodel.core import StructuredNode
from neomodel.exceptions import InflateConflict, DeflateConflict
from neomodel.util import _get_node_properties


class SemiStructuredNode(StructuredNode):
    """
    A base class allowing properties to be stored on a node that aren't
    specified in its definition. Conflicting properties are signaled with the
    :class:`DeflateConflict` exception::

        class Person(SemiStructuredNode):
            name = StringProperty()
            age = IntegerProperty()

            def hello(self):
                print("Hi my names " + self.name)

        tim = Person(name='Tim', age=8, weight=11).save()
        tim.hello = "Hi"
        tim.save() # DeflateConflict
    """
    __abstract_node__ = True

    def __init__(self, *args, **kwargs):
        super(SemiStructuredNode, self).__init__(*args, **kwargs)

    @classmethod
    def inflate(cls, node):
        # support lazy loading
        if isinstance(node, int):
            snode = cls()
            snode.id = node
        else:
            props = {}
            for key, prop in cls.__all_properties__:
                node_properties = _get_node_properties(node)
                if key in node_properties:
                    props[key] = prop.inflate(node_properties[key], node)
                elif prop.has_default:
                    props[key] = prop.default_value()
                else:
                    props[key] = None
            # handle properties not defined on the class
            for free_key in (x for x in node_properties if x not in props):
                if hasattr(cls, free_key):
                    raise InflateConflict(cls, free_key,
                                          node_properties[free_key], node.id)
                props[free_key] = node_properties[free_key]

            snode = cls(**props)
            snode.id = node.id

        return snode

    @classmethod
    def deflate(cls, node_props, obj=None, skip_empty=False):
        deflated = super(SemiStructuredNode, cls).deflate(node_props, obj,
                                                          skip_empty=skip_empty)
        for key in [k for k in node_props if k not in deflated]:
            if hasattr(cls, key):
                raise DeflateConflict(cls, key, deflated[key], obj.id)
        node_props.update(deflated)
        return node_props
