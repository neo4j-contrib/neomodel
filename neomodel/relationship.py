from neomodel.bases import PropertyManager, PropertyManagerMeta
from neomodel.db import client
from neomodel.hooks import hooks
from neomodel.types import RelationshipType


class RelationshipMeta(PropertyManagerMeta):
    def _setup_property(mcs, cls, name, instance):
        if instance.is_indexed:
            raise NotImplemented("Indexed relationship properties not supported yet")
        super()._setup_property(mcs, cls, name, instance)


class StructuredRel(PropertyManager, RelationshipType, metaclass=RelationshipMeta):
    """
    Base class for relationship objects
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @hooks
    def save(self):
        """
        Save the relationship

        :return: self
        """
        props = self.deflate(self.__properties__)
        query = "MATCH ()-[r]->() WHERE id(r)={self} "
        for key in props:
            query += " SET r.{} = {{{}}}".format(key, key)
        props['self'] = self.id

        client.cypher_query(query, props)

        return self

    def start_node(self):
        """
        Get start node

        :return: StructuredNode
        """
        node = self._start_node_class()
        node.id = self._start_node_id
        node.refresh()
        return node

    def end_node(self):
        """
        Get end node

        :return: StructuredNode
        """
        node = self._end_node_class()
        node.id = self._end_node_id
        node.refresh()
        return node

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
        srel._start_node_id = rel.start
        srel._end_node_id = rel.end
        srel.id = rel.id
        return srel
