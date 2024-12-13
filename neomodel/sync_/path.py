from collections.abc import Iterator

from neo4j.graph import Path

from neomodel.sync_.core import StructuredNode, db
from neomodel.sync_.relationship import StructuredRel


class NeomodelPath(object):
    """
    Represents paths within neomodel.

    This object is instantiated when you include whole paths in your ``cypher_query()``
    result sets and turn ``resolve_objects`` to True.

    That is, any query of the form:
    ::

        MATCH p=(:SOME_NODE_LABELS)-[:SOME_REL_LABELS]-(:SOME_OTHER_NODE_LABELS) return p

    ``NeomodelPath`` are simple objects that reference their nodes and relationships, each of which is already
    resolved to their neomodel objects if such mapping is possible.


    :param nodes: Neomodel nodes appearing in the path in order of appearance.
    :param relationships: Neomodel relationships appearing in the path in order of appearance.
    :type nodes: list[StructuredNode]
    :type relationships: list[StructuredRel]
    """

    def __init__(self, a_neopath: Path):
        self._nodes: list[StructuredNode] = []
        self._relationships: list[StructuredRel] = []

        for a_node in a_neopath.nodes:
            self._nodes.append(db._object_resolution(a_node))

        for a_relationship in a_neopath.relationships:
            # This check is required here because if the relationship does not bear data
            # then it does not have an entry in the registry. In that case, we instantiate
            # an "unspecified" StructuredRel.
            rel_type = frozenset([a_relationship.type])
            if rel_type in db._NODE_CLASS_REGISTRY:
                new_rel = db._object_resolution(a_relationship)
            else:
                new_rel = StructuredRel.inflate(a_relationship)
            self._relationships.append(new_rel)

    def __repr__(self) -> str:
        return "<Path start=%r end=%r size=%s>" % (
            self.start_node,
            self.end_node,
            len(self),
        )

    def __len__(self) -> int:
        return len(self._relationships)

    def __iter__(self) -> Iterator[StructuredRel]:
        return iter(self._relationships)

    @property
    def nodes(self) -> list[StructuredNode]:
        return self._nodes

    @property
    def start_node(self) -> StructuredNode:
        """The first :class:`.StructuredNode` in this path."""
        return self._nodes[0]

    @property
    def end_node(self) -> StructuredNode:
        """The last :class:`.StructuredNode` in this path."""
        return self._nodes[-1]

    @property
    def relationships(self) -> list[StructuredRel]:
        return self._relationships
