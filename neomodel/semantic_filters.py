from typing import Union

class VectorFilter(object):
    """
    Represents a CALL db.index.vector.query* neo functions call within the OGM

    :param topk: The amount of objects returned by this vector filter.
    :type topk: int
    :param vector_attribute_name: The property name for vector indexed property on the searched object.
    :type vector_attribute_name: str
    :param threshold: Threshold for vector similarity.
    :type threshold: float
    :param candidate_vector: The vector you are finding the nearest topk neighbours for.
    :type candidate_vector: list[float]

    """

    def __init__(
            self, topk: int, vector_attribute_name: str, candidate_vector: list[float], threshold: Union[float, None] =  None
    ):
        self.topk = topk
        self.vector_attribute_name = vector_attribute_name
        self.threshold = threshold
        self.index_name = None
        self.node_set_label = None
        self.vector = candidate_vector

class FulltextFilter(object):
    """
    Represents a CALL db.index.fulltext.query* neo functon call within the OGM.
    :param query_strng: The string you are finding the nearest
    :type query_string: str
    :param freetext_attribute_name: The property name for the free text indexed property.
    :type fulltext_attribute_name: str
    :param threshold: Threshold for vector similarity.
    :type threshold: float
    :param topk: Amount to nodes to return
    :type topk: int

    """

    def __init__(self, query_string: str, fulltext_attribute_name: str, topk: int, threshold: Union[float, None] =  None
    ):
        self.topk = topk
        self.query_string = query_string
        self.fulltext_attribute_name = fulltext_attribute_name
        self.threshold = threshold
        self.index_name = None
        self.node_set_label = None
