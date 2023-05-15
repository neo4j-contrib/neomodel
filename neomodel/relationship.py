from .core import db
from .hooks import hooks
from .properties import Property, PropertyManager


class RelationshipMeta(type):
    def __new__(mcs, name, bases, dct):
        inst = super().__new__(mcs, name, bases, dct)
        for key, value in dct.items():
            if issubclass(value.__class__, Property):
                value.name = key
                value.owner = inst

                # support for 'magic' properties
                if hasattr(value, "setup") and hasattr(value.setup, "__call__"):
                    value.setup()
        return inst


StructuredRelBase = RelationshipMeta("RelationshipBase", (PropertyManager,), {})


class StructuredRel(StructuredRelBase):
    """
    Base class for relationship objects
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._start_node_id = 0
        self._end_node_id = 0
        self.id = 0

    @hooks
    def save(self):
        """
        Save the relationship

        :return: self
        """
        props = self.deflate(self.__properties__)
        query = "MATCH ()-[r]->() WHERE id(r)=$self "
        query += "".join([f" SET r.{key} = ${key}" for key in props])
        props["self"] = self.id

        db.cypher_query(query, props)

        return self

    def start_node(self):
        """
        Get start node

        :return: StructuredNode
        """
        return db.cypher_query(
            f"""
            MATCH (aNode)
            WHERE id(aNode)={self._start_node_id}
            RETURN aNode
            """,
            resolve_objects=True,
        )[0][0][0]

    def end_node(self):
        """
        Get end node

        :return: StructuredNode
        """
        return db.cypher_query(
            f"""
            MATCH (aNode)
            WHERE id(aNode)={self._end_node_id}
            RETURN aNode
            """,
            resolve_objects=True,
        )[0][0][0]

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
