from neo4j.graph import Path as NeoPath

class Path(NeoPath):
    """
    Represents paths within neomodel.

    Paths reference their nodes and relationships, each of which is already 
    resolved to their neomodel objects if such mapping is possible.
    """
    def __init__(self, nodes, *relationships):
        # Resolve node objects
        self._nodes = tuple(nodes)
        # Resolve relationship objects
        self._relationships = relationships

