from .properties import Property, PropertyManager
from .core import db
from .util import deprecated
from .hooks import hooks


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
    """
    Base class for relationship objects
    """
    def __init__(self, *args, **kwargs):
        super(StructuredRel, self).__init__(*args, **kwargs)

    @hooks
    def save(self):
        """
        Save the relationship

        :return: self
        """
        props = self.deflate(self.__properties__)
        query = "MATCH ()-[r]->() WHERE id(r)={self} "
        for key in props:
            query += " SET r.{0} = {{{1}}}".format(key, key)
        props['self'] = self.id

        db.cypher_query(query, props)

        return self

    @deprecated('This method will be removed in neomodel 4')
    def delete(self):
        raise NotImplemented("Can not delete relationships please use"
                             " 'disconnect'")

    def start_node(self):
        """
        Get start node

        :return: StructuredNode
        """
        return db.cypher_query("MATCH (aNode) "
                               "WHERE id(aNode)={nodeid} "
                               "RETURN aNode".format(nodeid=self._start_node_id),
                               resolve_objects = True)[0][0][0]
      
    def end_node(self):
        """
        Get end node

        :return: StructuredNode
        """
        return db.cypher_query("MATCH (aNode) "
                               "WHERE id(aNode)={nodeid} "
                               "RETURN aNode".format(nodeid=self._end_node_id),
                               resolve_objects = True)[0][0][0]

    @classmethod
    def inflate(cls, rel):
        """
        Inflate a neo4j_driver relationship object to a neomodel object
        :param rel:
        :return: StructuredRel
        """
        props = {}
        for key, prop in cls.defined_properties(aliases=False, rels=False).items():
            if key in rel:
                props[key] = prop.inflate(rel[key], obj=rel)
            elif prop.has_default:
                props[key] = prop.default_value()
            else:
                props[key] = None
        srel = cls(**props)
        srel._start_node_id = rel.start_node.id
        srel._end_node_id = rel.end_node.id
        srel.id = rel.id
        return srel
