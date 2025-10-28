from _typeshed import Incomplete

class VectorFilter:
    topk: Incomplete
    vector_attribute_name: Incomplete
    index_name: Incomplete
    node_set_label: Incomplete
    vector: Incomplete
    def __init__(self, topk: int, vector_attribute_name: str, candidate_vector: list[float]) -> None: ...

class FulltextFilter:
    query_string: Incomplete
    fulltext_attribute_name: Incomplete
    index_name: Incomplete
    node_set_label: Incomplete
    topk: Incomplete
    def __init__(self, query_string: str, fulltext_attribute_name: str, topk: int) -> None: ...
