import warnings

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
        self._start_node_element_id = 0
        self._end_node_element_id = 0

    @property
    def id(self):
        warnings.warn(
            "the id property is deprecated please use element_id",
            category=DeprecationWarning,
            stacklevel=1,
        )
        if hasattr(self, "element_id") and self.element_id:
            return self.element_id
        else:
            self.element_id = self.id
            return self.element_id

    @hooks
    def save(self):
        """
        Save the relationship

        :return: self
        """
        props = self.deflate(self.__properties__)
        query = f"MATCH ()-[r]->() WHERE {db.get_id_method()}(r)=$self "
        query += "".join([f" SET r.{key} = ${key}" for key in props])
        props["self"] = self.element_id

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
            WHERE {db.get_id_method()}(aNode)=$start_node_element_id
            RETURN aNode
            """,
            {"start_node_element_id": self._start_node_element_id},
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
            WHERE {db.get_id_method()}(aNode)=$end_node_element_id
            RETURN aNode
            """,
            {"end_node_element_id": self._end_node_element_id},
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
        srel._start_node_element_id = rel.start_node.element_id
        srel._end_node_element_id = rel.end_node.element_id
        if hasattr(rel, "element_id"):
            srel.element_id = rel.element_id
        elif hasattr(rel, "id"):
            srel.element_id = rel.id
        return srel
