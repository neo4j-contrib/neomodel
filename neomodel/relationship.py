import warnings

from .core import db
from .hooks import hooks
from .properties import Property, PropertyManager


class RelationshipMeta(type):
    def __new__(mcs, name, bases, dct):
        inst = super().__new__(mcs, name, bases, dct)
        for key, value in dct.items():
            if issubclass(value.__class__, Property):
                if key == "source" or key == "target":
                    raise ValueError(
                        "Property names 'source' and 'target' are not allowed as they conflict with neomodel internals."
                    )
                elif key == "id":
                    raise ValueError(
                        """
                            Property name 'id' is not allowed as it conflicts with neomodel internals.
                            Consider using 'uid' or 'identifier' as id is also a Neo4j internal.
                        """
                    )
                elif key == "element_id":
                    raise ValueError(
                        """
                            Property name 'element_id' is not allowed as it conflicts with neomodel internals.
                            Consider using 'uid' or 'identifier' as element_id is also a Neo4j internal.
                        """
                    )
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

    @property
    def element_id(self):
        return (
            int(self.element_id_property)
            if db.database_version.startswith("4")
            else self.element_id_property
        )

    @property
    def _start_node_element_id(self):
        return (
            int(self._start_node_element_id_property)
            if db.database_version.startswith("4")
            else self._start_node_element_id_property
        )

    @property
    def _end_node_element_id(self):
        return (
            int(self._end_node_element_id_property)
            if db.database_version.startswith("4")
            else self._end_node_element_id_property
        )

    # Version 4.4 support - id is deprecated in version 5.x
    @property
    def id(self):
        try:
            return int(self.element_id_property)
        except (TypeError, ValueError):
            raise ValueError(
                "id is deprecated in Neo4j version 5, please migrate to element_id. If you use the id in a Cypher query, replace id() by elementId()."
            )

    # Version 4.4 support - id is deprecated in version 5.x
    @property
    def _start_node_id(self):
        try:
            return int(self._start_node_element_id_property)
        except (TypeError, ValueError):
            raise ValueError(
                "id is deprecated in Neo4j version 5, please migrate to element_id. If you use the id in a Cypher query, replace id() by elementId()."
            )

    # Version 4.4 support - id is deprecated in version 5.x
    @property
    def _end_node_id(self):
        try:
            return int(self._end_node_element_id_property)
        except (TypeError, ValueError):
            raise ValueError(
                "id is deprecated in Neo4j version 5, please migrate to element_id. If you use the id in a Cypher query, replace id() by elementId()."
            )

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
        test = db.cypher_query(
            f"""
            MATCH (aNode)
            WHERE {db.get_id_method()}(aNode)=$start_node_element_id
            RETURN aNode
            """,
            {"start_node_element_id": self._start_node_element_id},
            resolve_objects=True,
        )
        return test[0][0][0]

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
        srel._start_node_element_id_property = rel.start_node.element_id
        srel._end_node_element_id_property = rel.end_node.element_id
        srel.element_id_property = rel.element_id
        return srel
