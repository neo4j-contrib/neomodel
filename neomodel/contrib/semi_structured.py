from ..core import StructuredNode


class InflateConflict(Exception):
    def __init__(self, cls, key, value, nid):
        self.cls_name = cls.__name__
        self.property_name = key
        self.value = value
        self.nid = nid

    def __str__(self):
        return """Found conflict with node {0}, has property '{1}' with value '{2}'
            although class {3} already has a property '{1}'""".format(
            self.nid, self.property_name, self.value, self.cls_name)


class DeflateConflict(InflateConflict):
    def __init__(self, cls, key, value, nid):
        self.cls_name = cls.__name__
        self.property_name = key
        self.value = value
        self.nid = nid if nid else '(unsaved)'

    def __str__(self):
        return """Found trying to set property '{1}' with value '{2}' on node {0}
            although class {3} already has a property '{1}'""".format(
            self.nid, self.property_name, self.value, self.cls_name)


class SemiStructuredNode(StructuredNode):
    """
    A base class allowing properties to be stored on a node that aren't specified in it's definition.
    Conflicting properties are avoided through the DeflateConflict exception::

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
        props = {}
        for key, prop in cls.defined_properties(aliases=False, rels=False).items():
            if key in node._properties:
                props[key] = prop.inflate(node._properties[key])
            elif prop.has_default:
                props[key] = prop.default_value()
            else:
                props[key] = None
        # handle properties not defined on the class
        for free_key in [key for key in node._properties if key not in props]:
            if hasattr(cls, free_key):
                raise InflateConflict(cls, free_key, node._properties[free_key], node._id)
            props[free_key] = node._properties[free_key]

        snode = cls(**props)
        snode._id = node._id
        return snode

    @classmethod
    def deflate(cls, node_props, obj=None):
        deflated = super(SemiStructuredNode, cls).deflate(node_props, obj)
        for key in [k for k in node_props if k not in deflated]:
            if hasattr(cls, key):
                raise DeflateConflict(cls, key, deflated[key], obj._id)
        node_props.update(deflated)
        return node_props
