from typing import List

class VectorFilter():
    """
    UNDERCONSTRUCTION

    Represents a CALL db.index.vector.query* neo functions call within the OGM - to allow for a neomodel query method that isnt running the function within a query_cyphe call. 

    """
    def __init__(self, topk: int, index_name: str, candidate_vector: List[float], score: str):

        self.topk = topk
        self.index_name = index_name
        self.vector = candidate_vector
        self.score = score # The score here is actually a django filtered string

