from abc import ABC, abstractmethod

from neomodel.constants import (
    VERSION_FULLTEXT_SEARCH_CLAUSE_SUPPORT,
    VERSION_VECTOR_SEARCH_CLAUSE_SUPPORT,
)
from neomodel.properties import Property
from neomodel.util import escape_identifier


class SemanticFilter(ABC):
    """
    Base class for semantic (vector and fulltext) index search filters.

    A semantic filter describes a query against a vector or fulltext index. The
    two index kinds produce almost identical Cypher, differing only in the index
    keyword, the value being searched and the legacy procedure used before the
    Cypher 25 SEARCH clause was available. Those differences are captured by the
    underscore-prefixed hooks below so the query builder can treat every filter
    uniformly.
    """

    _search_clause_supported_version: str = ""
    _index_kind: str = ""
    _legacy_procedure: str = ""
    _index_name_prefix: str = ""
    _node_set_label: str = ""
    _index_name: str = ""
    _use_search_clause: bool = True

    def __init__(self, topk: int, threshold: float | None = None):
        self.topk: int = topk
        self.threshold: float | None = threshold
        self._index_name: str = ""
        self._node_set_label: str = ""
        self._use_search_clause: bool = True

    @property
    @abstractmethod
    def _attribute_name(self) -> str:
        """The name of the indexed property on the searched class."""
        pass

    @abstractmethod
    def _is_indexed(self, attribute: Property) -> bool:
        """Whether the given property is declared with this kind of index."""
        pass

    @abstractmethod
    def _search_value(self) -> str:
        """The Cypher expression for the ``FOR`` clause of the SEARCH subclause."""
        pass

    @abstractmethod
    def _legacy_procedure_args(self) -> str:
        """The arguments passed to the legacy query procedure."""
        pass

    def _threshold_where_statement(self) -> str:
        if self.threshold:
            return f"""score >= {self.threshold}"""
        else:
            return ""

    @abstractmethod
    def _build_legacy_call(self, node_set_label: str) -> str:
        pass

    @abstractmethod
    def _build_search_stmt(self, node_set_label: str) -> str:
        pass


class VectorFilter(SemanticFilter):
    """
    Represents a CALL db.index.vector.query* neo functions call within the OGM for neo4j_version < 2026.01.
    Otherwise, represents a SEARCH clause on the vector index for neo4j_version >= 2026.01.

    :param topk: The amount of objects returned by this vector filter.
    :type topk: int
    :param vector_attribute_name: The property name for vector indexed property on the searched object.
    :type vector_attribute_name: str
    :param threshold: Threshold for vector similarity.
    :type threshold: float
    :param candidate_vector: The vector you are finding the nearest topk neighbours for.
    :type candidate_vector: list[float]

    """

    _search_clause_supported_version = VERSION_VECTOR_SEARCH_CLAUSE_SUPPORT
    _index_kind = "VECTOR INDEX"
    _legacy_procedure = "db.index.vector.queryNodes"
    _index_name_prefix = "vector_index"

    def __init__(
        self,
        topk: int,
        vector_attribute_name: str,
        candidate_vector: list[float],
        threshold: float | None = None,
    ):
        super().__init__(topk, threshold)
        self.vector_attribute_name: str = vector_attribute_name
        self.vector: list[float] = candidate_vector

    @property
    def _attribute_name(self) -> str:
        return self.vector_attribute_name

    def _is_indexed(self, attribute: Property) -> bool:
        return bool(attribute.vector_index)

    def _search_value(self) -> str:
        return f"{self.vector}"

    def _legacy_procedure_args(self) -> str:
        return f'"{self._index_name}", {self.topk}, {self.vector}'

    def _build_legacy_call(self, node_set_label: str) -> str:
        node_set_label = escape_identifier(node_set_label)
        legacy_query = ""
        legacy_query += f"""CALL () {{
            CALL {self._legacy_procedure}({self._legacy_procedure_args()})
            YIELD node AS {node_set_label}, score"""
        if self.threshold:
            legacy_query += f""" WHERE {self._threshold_where_statement()}"""

        legacy_query += f"""
            RETURN {node_set_label}, score
            }}
            WITH {node_set_label}, score"""

        return legacy_query

    def _build_search_stmt(self, node_set_label: str) -> str:
        node_set_label = escape_identifier(node_set_label)
        search = f"""SEARCH {node_set_label} IN (
            VECTOR INDEX {escape_identifier(self._index_name)}
            FOR {self._search_value()}
            LIMIT {self.topk}
        ) SCORE AS score"""
        return search


class FulltextFilter(SemanticFilter):
    """
    Represents a CALL db.index.fulltext.query* neo functions call within the OGM for neo4j_version < 2026.09.
    Otherwise, represents a SEARCH clause on the fulltext index for neo4j_version >= 2026.09.

    :param query_string: The string you are finding the nearest
    :type query_string: str
    :param fulltext_attribute_name: The property name for the fulltext indexed property.
    :type fulltext_attribute_name: str
    :param threshold: Threshold for similarity.
    :type threshold: float
    :param topk: Amount of nodes to return
    :type topk: int

    """

    _search_clause_supported_version = VERSION_FULLTEXT_SEARCH_CLAUSE_SUPPORT
    _index_kind = "FULLTEXT INDEX"
    _legacy_procedure = "db.index.fulltext.queryNodes"
    _index_name_prefix = "fulltext_index"

    def __init__(
        self,
        query_string: str,
        fulltext_attribute_name: str,
        topk: int,
        threshold: float | None = None,
    ):
        super().__init__(topk, threshold)
        self.query_string: str = query_string
        self.fulltext_attribute_name: str = fulltext_attribute_name

    @property
    def _attribute_name(self) -> str:
        return self.fulltext_attribute_name

    def _is_indexed(self, attribute: Property) -> bool:
        return bool(attribute.fulltext_index)

    def _search_value(self) -> str:
        return f'"{self.query_string}"'

    def _legacy_procedure_args(self) -> str:
        return f'"{self._index_name}", "{self.query_string}"'

    def _build_legacy_call(self, node_set_label: str) -> str:
        node_set_label = escape_identifier(node_set_label)
        legacy_query = ""
        legacy_query += f"""CALL () {{
            CALL {self._legacy_procedure}({self._legacy_procedure_args()})
            YIELD node AS {node_set_label}, score"""
        if self.threshold:
            legacy_query += f""" WHERE {self._threshold_where_statement()}"""

        legacy_query += f"""
            RETURN {node_set_label}, score LIMIT {self.topk}
            }}
            WITH {node_set_label}, score"""

        return legacy_query

    def _build_search_stmt(self, node_set_label: str) -> str:
        node_set_label = escape_identifier(node_set_label)
        search = f"""SEARCH {node_set_label} IN (
            FULLTEXT INDEX {escape_identifier(self._index_name)}
            FOR {self._search_value()}
            LIMIT {self.topk}
        ) SCORE AS score"""
        return search
