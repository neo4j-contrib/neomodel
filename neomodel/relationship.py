from .properties import Property, PropertyManager
from .core import db


class RelationshipMeta(type):
    def __new__(mcs, name, bases, dct):
        inst = super(RelationshipMeta, mcs).__new__(mcs, name, bases, dct)
        for key, value in dct.items():
            if issubclass(value.__class__, Property):
                value.name = key
                value.owner = inst
                if value.is_indexed:
                    raise NotImplemented("Indexed relationship properties not supported yet")

                # support for 'magic' properties
                if hasattr(value, 'setup') and hasattr(value.setup, '__call__'):
                    value.setup()
        return inst


StructuredRelBase = RelationshipMeta('RelationshipBase', (PropertyManager,), {})


class StructuredRel(StructuredRelBase):
    def __init__(self, *args, **kwargs):
        super(StructuredRel, self).__init__(*args, **kwargs)

    def save(self):
        props = self.deflate(self.__properties__)
        query = "START r=relationship({self})"
        for key in props:
            query += " SET r.{} = {{{}}}".format(key, key)
        props['self'] = self._id

        db.cypher_query(query, props)

        return self

    def delete(self):
        raise NotImplemented("Can not delete relationships please use 'disconnect'")

    def start_node(self):
        node = self._start_node_class()
        node._id = self._start_node_id
        node.refresh()
        return node

    def end_node(self):
        node = self._end_node_class()
        node._id = self._end_node_id
        node.refresh()
        return node

    @classmethod
    def inflate(cls, rel):
        props = {}
        for key, prop in cls.defined_properties(aliases=False, rels=False).items():
            if key in rel._properties:
                props[key] = prop.inflate(rel._properties[key], obj=rel)
            elif prop.has_default:
                props[key] = prop.default_value()
            else:
                props[key] = None
        srel = cls(**props)
        srel._start_node_id = rel._start_node_id
        srel._end_node_id = rel._end_node_id
        srel._id = rel._id
        return srel
