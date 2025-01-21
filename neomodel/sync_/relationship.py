from typing import Any, Optional

from neo4j.graph import Relationship

from neomodel.hooks import hooks
from neomodel.properties import Property
from neomodel.sync_.core import db
from neomodel.sync_.property_manager import PropertyManager

ELEMENT_ID_MIGRATION_NOTICE = "id is deprecated in Neo4j version 5, please migrate to element_id. If you use the id in a Cypher query, replace id() by elementId()."


class RelationshipMeta(type):
    def __new__(
        mcs: type, name: str, bases: tuple[type, ...], dct: dict[str, Any]
    ) -> Any:
        inst: RelationshipMeta = type.__new__(mcs, name, bases, dct)
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


class StructuredRelBase(PropertyManager, metaclass=RelationshipMeta):
    pass


class StructuredRel(StructuredRelBase):
    """
    Base class for relationship objects
    """

    def __init__(self, *args: Any, **kwargs: dict) -> None:
        super().__init__(*args, **kwargs)

    @property
    def element_id(self) -> Optional[Any]:
        if hasattr(self, "element_id_property"):
            return self.element_id_property
        return None

    @property
    def _start_node_element_id(self) -> Optional[Any]:
        if hasattr(self, "_start_node_element_id_property"):
            return self._start_node_element_id_property
        return None

    @property
    def _end_node_element_id(self) -> Optional[Any]:
        if hasattr(self, "_end_node_element_id_property"):
            return self._end_node_element_id_property
        return None

    # Version 4.4 support - id is deprecated in version 5.x
    @property
    def id(self) -> int:
        try:
            return int(self.element_id_property)
        except (TypeError, ValueError) as exc:
            raise ValueError(ELEMENT_ID_MIGRATION_NOTICE) from exc

    # Version 4.4 support - id is deprecated in version 5.x
    @property
    def _start_node_id(self) -> int:
        try:
            return int(self._start_node_element_id_property)
        except (TypeError, ValueError) as exc:
            raise ValueError(ELEMENT_ID_MIGRATION_NOTICE) from exc

    # Version 4.4 support - id is deprecated in version 5.x
    @property
    def _end_node_id(self) -> int:
        try:
            return int(self._end_node_element_id_property)
        except (TypeError, ValueError) as exc:
            raise ValueError(ELEMENT_ID_MIGRATION_NOTICE) from exc

    @hooks
    def save(self) -> "StructuredRel":
        """
        Save the relationship

        :return: self
        """
        props = self.deflate(self.__properties__)
        query = f"MATCH ()-[r]->() WHERE {db.get_id_method()}(r)=$self "
        query += "".join([f" SET r.{key} = ${key}" for key in props])
        props["self"] = db.parse_element_id(self.element_id)

        db.cypher_query(query, props)

        return self

    def start_node(self) -> Any:
        """
        Get start node

        :return: StructuredNode
        """
        results = db.cypher_query(
            f"""
            MATCH (aNode)
            WHERE {db.get_id_method()}(aNode)=$start_node_element_id
            RETURN aNode
            """,
            {"start_node_element_id": db.parse_element_id(self._start_node_element_id)},
            resolve_objects=True,
        )
        if results is None or results[0] is None or results[0][0] is None:
            raise ValueError(
                f"Start node with elementId {self._start_node_element_id} not found"
            )
        return results[0][0][0]

    def end_node(self) -> Any:
        """
        Get end node

        :return: StructuredNode
        """
        results = db.cypher_query(
            f"""
            MATCH (aNode)
            WHERE {db.get_id_method()}(aNode)=$end_node_element_id
            RETURN aNode
            """,
            {"end_node_element_id": db.parse_element_id(self._end_node_element_id)},
            resolve_objects=True,
        )
        if results is None or results[0] is None or results[0][0] is None:
            raise ValueError(
                f"Start node with elementId {self._start_node_element_id} not found"
            )
        return results[0][0][0]

    @classmethod
    def inflate(cls: Any, rel: Relationship) -> "StructuredRel":
        """
        Inflate a neo4j_driver relationship object to a neomodel object
        :param rel:
        :return: StructuredRel
        """
        srel = super().inflate(rel)
        if rel.start_node is not None:
            srel._start_node_element_id_property = rel.start_node.element_id
        if rel.end_node is not None:
            srel._end_node_element_id_property = rel.end_node.element_id
        srel.element_id_property = rel.element_id
        return srel
