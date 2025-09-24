from typing import List

class VectorFilter(object):
    """
    Represents a CALL db.index.vector.query* neo functions call within the OGM
    
    :param topk: The amount of objects returned by this vector filter. 
    :type topk: int
    :param vector_attribute_name: The property name for vector indexed property on the searched object.
    :type vector_attribute_name: str
    :param candidate_vector: The vector you are finding the nearest topk neighbours for. 
    :type candidate_vector: list[float]

    """
    def __init__(self, topk: int, vector_attribute_name: str, candidate_vector: List[float]):
        self.topk = topk
        self.vector_attribute_name = vector_attribute_name
        self.index_name = None 
        self.nodeSetLabel = None
        self.vector = candidate_vector
        
