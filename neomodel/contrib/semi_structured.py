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
        # support lazy loading
        if isinstance(node, int):
            snode = cls()
            snode.id = node
        else:
            props = {}
            for key, prop in cls.__all_properties__:
                if key in node.properties:
                    props[key] = prop.inflate(node.properties[key], node)
                elif prop.has_default:
                    props[key] = prop.default_value()
                else:
                    props[key] = None
            # handle properties not defined on the class
            for free_key in [key for key in node.properties if key not in props]:
                if hasattr(cls, free_key):
                    raise InflateConflict(cls, free_key, node.properties[free_key], node.id)
                props[free_key] = node.properties[free_key]

            snode = cls(**props)
            snode.id = node.id

        return snode

    @classmethod
    def deflate(cls, node_props, obj=None, skip_empty=False):
        deflated = super(SemiStructuredNode, cls).deflate(node_props, obj, skip_empty=skip_empty)
        for key in [k for k in node_props if k not in deflated]:
            if hasattr(cls, key):
                raise DeflateConflict(cls, key, deflated[key], obj.id)
        node_props.update(deflated)
        return node_props
