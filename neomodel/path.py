from neo4j.graph import Path
from .core import db
from .relationship import StructuredRel
from .exceptions import RelationshipClassNotDefined


class NeomodelPath(Path):
    """
    Represents paths within neomodel.

    Paths reference their nodes and relationships, each of which is already 
    resolved to their neomodel objects if such mapping is possible.
    """
    def __init__(self, a_neopath):
        self._nodes=[]
        self._relationships = []

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
            # import pdb
            # pdb.set_trace()
            # try:
            #     new_rel = db._object_resolution(a_relationship)
            # except RelationshipClassNotDefined:
            #     new_rel = StructuredRel.inflate(a_relationship)
            #                
            self._relationships.append(new_rel)

