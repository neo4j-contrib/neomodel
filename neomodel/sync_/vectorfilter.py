from typing import List

class VectorFilter(object):
    """
    UNDERCONSTRUCTION

    Represents a CALL db.index.vector.query* neo functions call within the OGM - to allow for a neomodel query method that isnt running the function within a query_cyphe call. 
    
    The keyword argument for this in the filter function is: vector_filter (when we do the fulltextindex filter thing we should change this to be like index_filter or something so that we dont need to do this twice)
    """
    def __init__(self, topk: int, vector_attribute_name: str, candidate_vector: List[float]):
        self.topk = topk
        self.vector_attribute_name = vector_attribute_name
        self.index_name = None 
        self.vector = candidate_vector
        
