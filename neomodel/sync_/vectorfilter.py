from typing import List

class VectorFilter(object):
    """
    UNDERCONSTRUCTION

    Represents a CALL db.index.vector.query* neo functions call within the OGM - to allow for a neomodel query method that isnt running the function within a query_cyphe call. 
    
    The keyword argument for this in the filter function is: vector_filter (when we do the fulltextindex filter thing we should change this to be like index_filter or something so that we dont need to do this twice)
    This currently works, like it returns the correct node, but I need to determeine how to get it to return the score alongside it.
    This DOESNT work, when another filter is provided in alongside it. The vector index call is not being AND'd with the rest of the filters, the bottom filter seems to just 'take over'
    """
    def __init__(self, topk: int, index_name: str, candidate_vector: List[float]):
        # Not doing score thresholding because I dont know how to DJANGO filters.
        self.topk = topk
        self.index_name = index_name
        self.vector = candidate_vector

